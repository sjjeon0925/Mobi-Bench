## Downbload

you can download the dataset from the [Drive link](https://drive.google.com/drive/folders/11MaohFL5ggQGJEQWtbnjOzCb67z1Ff2E?usp=sharing)


## Dataset Structure
```shell
Benchmark Dataset
│
├── <task_1>
│       |── 0.png
│       |── 0.xml
│       |── 0_answers.json
│       |── 1.png
│       |── 1.xml
│       |── 1_answers.json
│       |── 2.png
│       |── 2.xml
│       |── 2_answers.json
│       |── <instruction.json>
└── <task_2>
│       |── 0.png
│       |── 0.xml
│       |── 0_answers.json
│       |── <instruction.json>
└── <task_3>
└── <task_4>
└── <task_5>
└── ...
└── <task_n>
```

Dataset folder contains different ground-truth traces named *task_[n]*, comprising the following files, sorted by index i starting from 0:

- *i*.png: Screenshot of the current UI
- *i*.xml: View hierarchy captured using the `adb uiautomator dump` command
- *i_answers*.json: default or non-default answer of each steps
- instruction.txt: Episode (a string uniquely representing the task) and task description

## JSON Structure
+ **JSON Structure Explanation**: 
    + **N_ansers**: Contains an array of steps to complete the instruction.

```json
[
    {
        "type": "<type>",
        "bounds": "boundary of action box",
        "params": {"<Parameter of actions>"},
        "default": "<defalt action or not>"
    },
    {
        "type": "Click",
        "bounds": "[933,2219][1038,2324]",
        "params": {},
        "default": false
    }
]
```
