import abc
import base64
import io
import os
import json
import time
import requests
import numpy as np
from typing import Any, Optional
from PIL import Image
from openai import OpenAI

from utils import log

# Support comma-separated keys: pick the first non-empty (strip quotes)
def _pick_first_key(env_name: str) -> str | None:
    raw = os.environ.get(env_name, "") or ""
    for part in raw.split(","):
        key = part.strip().strip('"').strip("'")
        if not key:
            continue
        # Allow indirection: if the token matches another env var name, use its value
        resolved = os.environ.get(key, key)
        resolved = resolved.strip().strip('"').strip("'")
        if resolved:
            return resolved
    return None

API_KEY = _pick_first_key("OPENROUTER_API_KEY")
OPENAI_API_KEY = _pick_first_key("OPENAI_API_KEY")

if not API_KEY:
    raise ValueError(
        "OPENROUTER_API_KEY 환경 변수가 설정되지 않았습니다.\n"
        "OpenRouter API 키를 OPENROUTER_API_KEY 환경 변수에 설정해주세요."
    )


def array_to_jpeg_bytes(image: np.ndarray) -> bytes:
    """Converts a numpy array into a byte string for a JPEG image."""
    image = Image.fromarray(image)
    return image_to_jpeg_bytes(image)


def image_to_jpeg_bytes(image: Image.Image) -> bytes:
    if image.mode == "RGBA":
        image = image.convert("RGB")
    in_mem_file = io.BytesIO()
    image.save(in_mem_file, format="JPEG")
    in_mem_file.seek(0)
    return in_mem_file.read()


class Model(abc.ABC):
    def __init__(self, name: str):
        self.name = name

    @abc.abstractmethod
    def query(self, prompt: str, conversation: Optional[list[dict]] = None) -> str:
        pass

    def query_mm(
        self,
        prompt: str,
        conversation: Optional[list[dict]] = None,
        images: Optional[list[Image.Image]] = None,
    ) -> str:
        pass


class GPTWrapper(Model):
    def __init__(self, name: str, temperature: float = 0.0, reasoning_effort: str = "low"):
        super().__init__(name)
        self.model_name = name
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort or "low"

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=API_KEY,
        )
        # Native OpenAI client for GPT-5.1 responses API
        self.native_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

    def _run_gpt51(self, prompt: str, model_override: str | None = None) -> tuple[str, dict]:
        """Call GPT-5.x via OpenAI responses API with reasoning effort low."""
        if not self.native_client:
            raise ValueError("OPENAI_API_KEY is required for gpt-5.1 responses API.")
        target_model = model_override or "gpt-5.1"
        resp = self.native_client.responses.create(
            model=target_model,
            input=prompt,
            reasoning={"effort": self.reasoning_effort},
            text={"verbosity": "low"},
        )
        result = getattr(resp, "output_text", "") or ""
        return result, {"reasoning_effort": self.reasoning_effort, "model": target_model, "response": resp}

    def query(self, prompt: str, conversation: Optional[list[dict]] = None) -> str:
        """Queries the language model with a text prompt."""
        # gpt-5.1: use native responses API
        if "gpt-5.1" in self.model_name:
            try:
                result, meta = self._run_gpt51(prompt, model_override=self.model_name)
                log(f"[reasoning: {self.reasoning_effort}] {result}", "green")
                return result, meta
            except Exception as e:
                log(f"gpt-5.1 request failed: {e}", "red")
                return "", {}
        # gpt-5: also use responses API (no images)
        if "gpt-5" in self.model_name:
            try:
                result, meta = self._run_gpt51(prompt, model_override=self.model_name)
                log(f"[reasoning: {self.reasoning_effort}] {result}", "green")
                return result, meta
            except Exception as e:
                log(f"gpt-5 request failed: {e}", "red")
                return "", {}

        messages = []
        if conversation:
            for i, message in enumerate(conversation):
                messages.append(
                    {
                        "role": "user" if i % 2 == 0 else "assistant",
                        "content": message["text"],
                    }
                )
        messages.append({"role": "user", "content": prompt})
        for message in messages:
            log("--------------------------")
            log(message["content"], "yellow")

        response = self.client.chat.completions.create(
            model=self.model_name,
            temperature=1,
            messages=messages,
        )
        result = response.choices[0].message.content.strip()
        log(result, "green")
        headers = response.response_headers
        return result, headers

    def gen_content(self, text: str, images: Optional[Any] = None) -> list[dict]:
        """Builds multi-modal content list for chat messages."""
        content = [{"type": "text", "text": text}]
        if images is None:
            return content
        from PIL import Image as _PILImage

        if isinstance(images, _PILImage.Image):
            image_list = [images]
        elif isinstance(images, (list, tuple)):
            image_list = [im for im in images if isinstance(im, _PILImage.Image)]
            if not image_list:
                return content
        else:
            return content

        for im in image_list:
            img_bytes = image_to_jpeg_bytes(im)
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
            )
        return content

    def query_mm(
        self,
        prompt: str,
        images: Optional[list[Image.Image]] = None,
        conversation: Optional[list[dict]] = None,
    ) -> str:
        """Queries the language model with a text prompt and optional images."""
        # gpt-5.1: use native responses API (images ignored)
        if "gpt-5.1" in self.model_name:
            try:
                result, meta = self._run_gpt51(prompt, model_override=self.model_name)
                log(f"[reasoning: {self.reasoning_effort}] {result}", "green")
                return result, meta
            except Exception as e:
                log(f"gpt-5.1 request failed: {e}", "red")
                return "", {}
        # gpt-5: also use responses API (images ignored)
        if "gpt-5" in self.model_name:
            try:
                result, meta = self._run_gpt51(prompt, model_override=self.model_name)
                log(f"[reasoning: {self.reasoning_effort}] {result}", "green")
                return result, meta
            except Exception as e:
                log(f"gpt-5 request failed: {e}", "red")
                return "", {}

        messages = []
        if conversation:
            for turn in conversation:
                role = turn.get("role", "user")
                if role == "user":
                    content = self.gen_content(turn.get("text", ""), turn.get("images"))
                else:
                    content = turn.get("text", "") or ""
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": self.gen_content(prompt, images)})

        response = None
        retry = 0
        max_retry = 3

        log(prompt, "yellow")

        while retry < max_retry:
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    extra_body={},
                    temperature=self.temperature,
                    top_p=0,
                    frequency_penalty=0,
                    presence_penalty=0,
                    stream=False,
                )

                if response and response.choices:
                    break
                else:
                    log(f"No choices in response (retry {retry+1})", "red")

            except Exception as e:
                log(f"Request failed (retry {retry+1}): {e}", "red")

            retry += 1
            time.sleep(2)

        if not response or not response.choices:
            log("All retries failed. Returning empty response.", "red")
            return "", {}

        time.sleep(2)
        result = response.choices[0].message.content.strip() if response.choices else ""

        generation_data = None
        retry = 0
        max_retry = 3
        generation_id = response.id
        header = {
            "Authorization": f"Bearer {API_KEY}",
        }
        while retry < max_retry and generation_data is None:
            try:
                generation_response = requests.get(
                    f"https://openrouter.ai/api/v1/generation?id={generation_id}",
                    headers=header,
                    timeout=10,
                )
                if generation_response.status_code == 200:
                    generation_data = generation_response.json().get("data", {})
                    if generation_data:
                        break
                log(f"Empty or invalid generation_data (retry {retry+1})", "red")

            except requests.exceptions.ConnectionError as e:
                log(f"Connection error (retry {retry+1}): {e}", "red")
            except Exception as e:
                log(f"Generation data request failed (retry {retry+1}): {e}", "red")

            retry += 1
            time.sleep(5)

        return result, generation_data
