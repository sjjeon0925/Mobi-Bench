# Standard library imports
import importlib
import gc
from collections.abc import Sequence

# Load environment variables FIRST before any other imports
from dotenv import load_dotenv
load_dotenv()

# Third-party imports
from absl import app, flags, logging

# Agent imports
from agent.base_agent import Agent
from agent.image_with_explanation.image_with_explanation_openR import ImageWithExplanationAgent
from agent.xml_only.xml_only_openR import XmlOnlyAgent
from agent.divandconq.divandconq import SeeActAgent
from agent.divandconq.divandconq_text import DivAndConqTextAgent
from agent.image_only.image_only import ImageOnlyAgent
from agent.gemini_cu.gemini_cu_agent import GeminiCUAgent

# Benchmark imports
from benchmark.agentbench.benchmark_agentbench import BenchmarkAgentBench

# Environment imports
from environment.base_env import Env
from environment.agentbench.agentbench_env import AgentBenchEnv

# Model imports
from model.base_model import Model, GPTWrapper

# Parser imports are loaded lazily inside _get_parser() to avoid heavy/optional deps at import time


# Flag definitions
_PARSER_NAME = flags.DEFINE_string("parser_name", "structured_xml", "The name of the parser to use")
_PROMPT_NAME = flags.DEFINE_string("prompt_name", "react", "The name of the prompt to use")
_AGENT_NAME = flags.DEFINE_string("agent_name", "image_with_explanation", "The name of the agent to use")
_MODEL_NAME = flags.DEFINE_string("model_name", "openai/gpt-4.1", "The name of the model to use")
_ENV_NAME = flags.DEFINE_string("env_name", "agentbench", "The name of the environment to use")
_BENCHMARK_NAME = flags.DEFINE_string("benchmark_name", "agentbench", "The name of the benchmark to use")
_SUMMARY_NAME = flags.DEFINE_string("summary_name", "pre", "The name of the summary to use")
_REFLECTION_NAME = flags.DEFINE_string("reflection_name", "no_reflection", "The name of the reflection to use")
_REFLECTION_MODEL_NAME = flags.DEFINE_string("reflection_model_name", "openai/gpt-4.1", "The name of the reflection model to use")
_SUMMARY_MODEL_NAME = flags.DEFINE_string("summary_model_name", "openai/gpt-4.1", "The name of the summary model to use")
_SOM_MODE = flags.DEFINE_string("som_mode", "som", "Whether to use som or nosom mode")
_SAVE_SCREENSHOTS = flags.DEFINE_bool("save_screenshots", True, "Whether to persist screenshots during execution")
_USE_M3A = flags.DEFINE_bool("m3a", False, "Use the m3a preset (react prompt, post summary, UI_element parser)")
_REASONING_EFFORT = flags.DEFINE_string(
    "reasoning_effort",
    "low",
    "Reasoning effort for gpt-5.1 (none|low|medium|high). Only used when model_name contains gpt-5.1.",
)


def load_prompt_module(prompt_name: str = None):
    """Load prompt module."""
    try:
        if prompt_name == "m3a":
            return importlib.import_module("prompts.agent_specific.m3a")
        return importlib.import_module("prompts.React")
    except ModuleNotFoundError:
        raise ImportError(f"No prompt module found for prompt: {prompt_name}")


def _get_parser():
    """Gets parser."""
    print("Initializing parser")
    parser = None
    if _PARSER_NAME.value == "structured_xml":
        from screen_parser.structured_xml.structured_xml_parser_v2 import StructuredXmlParser
        parser = StructuredXmlParser()
    elif _PARSER_NAME.value == "UI_element":
        from screen_parser.UI_element.UI_element_parser import UIElementParser
        parser = UIElementParser()
    elif _PARSER_NAME.value == "UI_caption":
        # This parser depends on ultralytics/YOLO; import only when selected
        from screen_parser.UI_caption.UI_caption_parser import UICaptionParser
        parser = UICaptionParser()
    else:
        raise ValueError(f"Unknown parser: {_PARSER_NAME.value}")
    return parser


def _get_model():
    """Initialize main model."""
    print("Initializing main model")
    return GPTWrapper(_MODEL_NAME.value, reasoning_effort=_REASONING_EFFORT.value)


def _get_reflection_model():
    """Initialize reflection model only if needed."""
    if _REFLECTION_NAME.value == "no_reflection":
        return None
    print("Initializing reflection model")
    # 메인 모델과 같으면 같은 인스턴스 재사용을 위해 나중에 처리
    return GPTWrapper(_REFLECTION_MODEL_NAME.value, reasoning_effort=_REASONING_EFFORT.value)


def _get_summary_model():
    """Initialize summary model only if needed."""
    if _SUMMARY_NAME.value in ["none", "no_summary"]:
        return None
    print("Initializing summary model")
    # 메인 모델과 같으면 같은 인스턴스 재사용을 위해 나중에 처리
    return GPTWrapper(_SUMMARY_MODEL_NAME.value, reasoning_effort=_REASONING_EFFORT.value)

def _optimize_model_instances(main_model, reflection_model, summary_model):
    """Optimize model instances to avoid duplicate creation for same model names."""
    # 같은 모델명이면 인스턴스 재사용
    if reflection_model and _REFLECTION_MODEL_NAME.value == _MODEL_NAME.value:
        reflection_model = main_model
        print("Reusing main model for reflection")
    
    if summary_model and _SUMMARY_MODEL_NAME.value == _MODEL_NAME.value:
        summary_model = main_model
        print("Reusing main model for summary")
    
    if (reflection_model and summary_model and 
        _REFLECTION_MODEL_NAME.value == _SUMMARY_MODEL_NAME.value and
        reflection_model != main_model):
        summary_model = reflection_model
        print("Reusing reflection model for summary")
    
    return main_model, reflection_model, summary_model


def _get_agent(env: Env, model: Model, summary_model: Model, reflection_model: Model, prompt, summary_type: str = "post", prompt_type: str = "react", reflection_type: str = "pre", som_mode: str = "som"):
    """Gets agent."""
    print("Initializing agent")
    agent = None
    if _AGENT_NAME.value == "image_with_explanation":
        agent = ImageWithExplanationAgent(model, reflection_model, summary_model, env, prompt, summary_type, prompt_type, reflection_type, som_mode=som_mode, save_screenshots=_SAVE_SCREENSHOTS.value)
    elif _AGENT_NAME.value == "xml_only":
        agent = XmlOnlyAgent(model, reflection_model, summary_model, env, prompt, summary_type, prompt_type, reflection_type, som_mode=som_mode, save_screenshots=_SAVE_SCREENSHOTS.value)
    elif _AGENT_NAME.value == "divandconq":
        agent = SeeActAgent(
            model,
            env,
            prompt,
            summary_type,
            reflection_type=reflection_type,
            som_mode=som_mode,
            save_screenshots=_SAVE_SCREENSHOTS.value,
            prompt_type=prompt_type,
            summary_model=summary_model,
            reflection_model=reflection_model,
        )
    elif _AGENT_NAME.value == "divandconq_text":
        agent = DivAndConqTextAgent(
            model,
            env,
            prompt,
            summary_type,
            reflection_type=reflection_type,
            prompt_type=prompt_type,
            summary_model=summary_model,
            reflection_model=reflection_model,
        )
    elif _AGENT_NAME.value == "image_only":
        # Image-only uses a simplified agent with no summaries/reflection
        agent = ImageOnlyAgent(
            model, 
            env, 
            prompt, 
            prompt_type=prompt_type
        )
    elif _AGENT_NAME.value == "gemini_cu":
        agent = GeminiCUAgent(
            model, 
            reflection_model, 
            summary_model, 
            env, 
            prompt, 
            summary_type=_SUMMARY_NAME.value, 
            prompt_type=_PROMPT_NAME.value, 
            reflection_type=_REFLECTION_NAME.value, 
            som_mode=_SOM_MODE.value, 
            save_screenshots=_SAVE_SCREENSHOTS.value
        )
    else:
        raise ValueError(f"Unknown agent: {_AGENT_NAME.value}")
    return agent


def _get_env():
    """Gets environment."""
    print("Initializing environment")
    if _ENV_NAME.value == 'agentbench':
        return AgentBenchEnv(_get_parser(), _ENV_NAME.value)
    else:
        raise ValueError(f"Unknown environment: {_ENV_NAME.value}")


def _get_benchmark(env: Env, agent: Agent):
    """Gets benchmark."""
    if _BENCHMARK_NAME.value == "agentbench":
        return BenchmarkAgentBench(_BENCHMARK_NAME.value, env, agent)
    else:
        raise ValueError(f"Unknown benchmark: {_BENCHMARK_NAME.value}")

def main(argv: Sequence[str]) -> None:
    """Main function to run experiments."""
    del argv
    prompt_name = _PROMPT_NAME.value
    summary_name = _SUMMARY_NAME.value
    parser_name = _PARSER_NAME.value
    prompt_type = _PROMPT_NAME.value

    if _USE_M3A.value:
        prompt_name = "m3a"
        summary_name = "post"
        parser_name = "UI_element"
        prompt_type = "react"
        flags.FLAGS["parser_name"].value = parser_name
        flags.FLAGS["summary_name"].value = summary_name
        flags.FLAGS["prompt_name"].value = prompt_name

    env = _get_env()

    # [추가] 결과 저장 경로 강제 지정 (TypeError 방지)
    import os
    if hasattr(env, 'results_path'):
        env.results_path = "results"
        os.makedirs(env.results_path, exist_ok=True)

    model = _get_model()
    reflection_model = _get_reflection_model()
    summary_model = _get_summary_model()

    model, reflection_model, summary_model = _optimize_model_instances(
        model, reflection_model, summary_model
    )

    prompt = load_prompt_module(prompt_name)
    agent = _get_agent(
        env,
        model,
        summary_model,
        reflection_model,
        prompt,
        summary_name,
        prompt_type,
        _REFLECTION_NAME.value,
        _SOM_MODE.value,
    )
    benchmark = _get_benchmark(env, agent)

    try:
        benchmark.run()

        print(f"\n{'='*50}")
        print("Cleaning up")
        print(f"{'='*50}\n")

        if hasattr(agent, 'history'):
            for step_data in agent.history:
                step_data['before_screenshot'] = None
                step_data['after_screenshot'] = None
                step_data['before_raw_screenshot'] = None
                step_data['after_raw_screenshot'] = None

        del benchmark
        del agent
        del env
        del model
        if reflection_model is not None:
            del reflection_model
        if summary_model is not None:
            del summary_model

    except Exception as e:
        print(f"\n[에러] 실행 중 오류 발생: {e}")

    gc.collect()
    print("Cleanup completed. Memory freed.\n")

if __name__ == "__main__":
    app.run(main)

