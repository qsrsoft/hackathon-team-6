"""
Form Converter using Direct Bedrock API Calls

This script demonstrates a two-step workflow:
1. Analyze a paper form image to extract field specifications
2. Generate HTML form markup from those specifications

Prerequisites:
- pip install boto3
- AWS credentials configured (aws configure)
- Enabled Claude 3.7 Sonnet model access in Amazon Bedrock
"""

import boto3
import json
import base64
from pathlib import Path

# Model configuration
MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
REGION = "us-west-2"

# Initialize Bedrock client
bedrock = boto3.client('bedrock-runtime', region_name=REGION)

# Form Analyzer Prompt
ANALYZER_PROMPT = """
You are analyzing a paper form image to extract field information for conversion to a digital form.

For each input field you identify, provide:
1. **label**: The exact text label as it appears on the form (or null if no label is present)
2. **suggested_label**: A cleaned-up, standardized version of the label suitable for a digital form
3. **type**: The most appropriate HTML input type (text, email, date, number, tel, url, textarea, file, checkbox, radio, select, etc.)

Analyze the form systematically from top to bottom, left to right.

Return your analysis as a JSON object with this structure:
{
  "fields": [
    {
      "label": "string or null",
      "suggested_label": "string",
      "type": "string"
    }
  ]
}

Important:
- Treat each input field separately, even if they appear grouped (e.g., First Name and Last Name are two separate fields)
- For suggested_label, use clear, concise labels following common form conventions
- Infer the most appropriate input type based on the label, placeholder text, or visual format
- Use standard HTML5 input types
- Return ONLY valid JSON with no markdown code blocks, no explanations, no additional text
- Your entire response must be a single valid JSON object and nothing else
"""

# Form Builder Prompt
BUILDER_PROMPT = """
You are a helpful assistant. You have two functions:
1. get current time
2. generate form json

for current time, just return a string with the current time. Nothing fancy

For form json, your job is to help users create forms by generating a JSON array of form field objects. You must always respond with valid JSON, containing only an array of objects where each object represents a form field (or layout element like headers or dividers).
You must return *ONLY* a JSON array - no extra text. Each object must contain fields based on the supported types listed below. All responses must follow the schema shown below.

### Question construction
**Supported Question Types**
| Question Type | Description |
|--------|--------|
| header | A non-answerable header |
| divider | A horizontal rule |
| spacer | Blank space for visual layout |
| section | Groups questions. Has a questions array attritbute. This can be used to visually put groups of questions together |
| image | A static image display |
| hyperlink | A clickable hyperlink |
| signature | A field for signature capture |
| stopwatch | A stopwatch timer with multiple tracked rows |
| temperature | Temperature recording with history |
| imageUpload | Upload an image |
| rating | A 1-5 star rating input |
| textShort | Short free-text answer |
| textLong | Long free-text answer |
| number | A numeric input |
| tally | Used for counting up other questions' points. Use groupIds for grouping |
| radio | Single choice (radio buttons) |
| checkbox | Multiple choice (checkboxes) |
| select | Dropdown menu of choices (single choice) |
| datePicker | Pick a calendar date |
| timePicker | Pick a time of day |


**General Attritubes**
Each question will have these attributes that you can modify:
| Key | type | Description |
|--------|--------|--------|
| title| string | the title of the qestion |
| type| string | the type of question |
| settings| object | a general catch-all for question settings |
| options| object[] | options to a question. radio, checkbox, select & stopwatch all use options |
| groupIds| string[] | an array of strings that group questions together. Two questions are in the same group if both of their groupIds include the same string |
| required| boolean | is the question required to be filled out before the form can be submitted? |
| enableComments| boolean | are comments enabled? |

**General Question Settings**
There are general settings that each question can use. They are optional
| key | description | possible values |
|--------|--------|--------|
| color | the color of the question's title | blue-low, blue-high, pink-low, pink-high, purple-low, purple-high, teal-low, teal-high, cyan-low, cyan-high, deep-orange-low, deep-orange-high, grey-low, grey-high, success-low, success-high, warning-low, warning-high, danger-low, danger-high |
| size | the font size of the question's title | small, medium, large |
| weight | the font weight of the question's title | normal, bold, lighter |

**colors can ONLY be from the list above. No hex or rgb values will work. Only the words "xx-low" or "xx-high" **

example:
```
settings: {
  "color": "purple-low",
  "size": "large",
  "weight": "lighter"
}
```

### Question JSON Output Examples
**header**
settings.headerType = header | subheader | description
```
{
  "title": "Example header",
  "type": "header",
  "settings": {
    "headerType": "subheader"
  }
}
```

**divider**
```
{
  "title": "New Divider",
  "type": "divider"
}
```

**spacer**
```
{
  "title": "New Spacer",
  "type": "spacer"
}
```

**image**
```
{
  "title": "New Image Display",
  "type": "image",
  "settings": {
    "caption": "example caption"
  }
}
```

**textShort**
```
{
  "title": "New Short Answer",
  "type": "textShort"
}
```

**textLong**
```
{
  "title": "New Long Answer",
  "type": "textLong"
}
```

**radio / select**
radio and select use the options. Each option needs a title and can optionally have points and a follow up question
```
{
  "title": "New Single Choice",
  "type": "radio",
  "options": [
    {
      "title": "Option 1"
    },
    {
      "title": "Option 2"
    }
  ]
}

// with points
{
  "title": "Will you get this correct?",
  "type": "select",
  "options": [
    {
      "title": "Yes",
      "points": 5
    },
    {
      "title": "No"
    }
  ]
}

// with follow up question
{
  "title": "Will you get this correct?",
  "type": "radio",
  "options": [
    {
      "title": "Yes",
      "points": 5
    },
    {
      "title": "No",
      "question": {
        "type": "textShort",
        "title": "Explain yourself"
      }
    }
  ]
}
```

**checkbox**
```
{
  "title": "New Multiple Choice",
  "type": "checkbox",
  "options": [
    {
      "title": "Option 1"
    },
    {
      "title": "Option 2"
    }
  ]
}

// checkbox with points and follow up
{
  "title": "What areas are dirty?",
  "type": "checkbox",
  "options": [
    {
      "title": "None",
      "points": 3
    },
    {
      "title": "Kitchen",
      "question": {
        "type": "textShort",
        "title": "What is dirty"
      }
    },
    {
      "title": "Bathroom",
      "question": {
        "type": "textShort",
        "title": "What is dirty"
      }
    }
  ]
}
```

**tally**
```
// example of a question and a tally counting the points for that question:
[
  {
    "title": "New Single Choice",
    "type": "radio",
    "options": [
      {
        "title": "Option 1",
        "points": 3
      },
      {
        "title": "Option 2"
      }
    ],
    "groupIds": [
      "51d3b82c-7d22-4bd6-9d97-dc0aa8af4a02"
    ]
  },
  {
    "title": "Tally",
    "type": "tally",
    "groupIds": [
      "51d3b82c-7d22-4bd6-9d97-dc0aa8af4a02"
    ]
  }
]

// example of a tally counting points for ALL questions in the form
{
  "title": "Tally",
  "type": "tally",
  "groupIds": [
    "ALL"
  ]
}
```

**number**
```
// basic usage
{
  "title": "New Number",
  "type": "number",
  "settings": {
    "minMax": false
  }
}

// min/max - points are assigned if they are within this range
{
  "title": "New Number",
  "type": "number",
  "settings": {
    "minMax": true,
    "points": 5,
    "min": 0,
    "max": 100
  }
}

// min/max - follow up. Follow ups are only shown if they are outside of the minmax range
{
  "title": "New Number",
  "type": "number",
  "settings": {
    "minMax": true,
    "points": 5,
    "min": 0,
    "max": 100
  },
  "followUpQuestion": {
    "type": "textShort",
    "title": "Follow Up for New Number"
  }
}
```

**datePicker**
```
{
  "title": "New Date Picker",
  "type": "datePicker"
}
```

**timePicker**
```
{
  "title": "New Time Picker",
  "type": "timePicker"
}
```

**imageUpload**
```
{
  "title": "New Image Upload",
  "type": "imageUpload"
}
```

**hyperlink**
```
{
  "title": "New Hyperlink",
  "type": "hyperlink",
  "settings": {
    "label": "google",
    "link": "https://www.google.com"
  }
}
```

**signature**
```
{
  "title": "New Signature",
  "type": "signature"
}
```

**section**
```
{
  "title": "New Section",
  "questions": [
    {
      "title": "New Multiple Choice",
      "type": "checkbox",
      "options": [
        {
          "title": "Option 1"
        },
        {
          "title": "Option 2"
        }
      ]
    }
  ]
}

```

### Best Practices
- if you have questions that can earn points, it is good practice to add a tally at the end of a group of questions, the section, or at the end of the whole form to count the points earned
- points on questions are only used for non opinionated forms. Asking "How are you?" should not have points. Asking "Is the kitchen clean?" can have points.
- groups of related questions should be colored the same to visually group them
- Yes/No questions should always be a radio type
- If a question answer is actionable, or needs more clarity, use a follow up (if the type supports it)
- sections should only have questions that are related together. All questions in the section should have matching colors to visually group the section
- a section should never be empty
- A good form is short and concise. People filling out the forms generally do not have time to fill out a novel. The max number of questions is 50.
"""


def call_claude(prompt, file_path=None):
    """
    Call Claude via Bedrock API.

    Args:
        prompt: Text prompt to send
        file_path: Optional path to image or PDF file

    Returns:
        Response text from Claude
    """
    content = []

    if file_path:
        with open(file_path, 'rb') as f:
            file_bytes = f.read()

        extension = Path(file_path).suffix.lower()

        if extension == '.pdf':
            content.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.b64encode(file_bytes).decode('utf-8')
                }
            })
        else:
            # Handle images
            media_type_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            media_type = media_type_map.get(extension, 'image/jpeg')

            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.b64encode(file_bytes).decode('utf-8')
                }
            })

    content.append({
        "type": "text",
        "text": prompt
    })

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4000,
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ]
    }

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(request_body)
    )

    response_body = json.loads(response['body'].read())
    response_text = response_body['content'][0]['text']

    return response_text


def clean_json_response(text):
    """Remove markdown code blocks from JSON response."""
    text = text.strip()
    if text.startswith('```json'):
        text = text[7:]
    elif text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    return text.strip()


def clean_html_response(text):
    """Remove markdown code blocks from HTML response."""
    text = text.strip()
    if text.startswith('```html'):
        text = text[7:]
    elif text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    return text.strip()


def analyze_form(image_path):
    """
    Analyze a paper form image and extract field specifications.

    Args:
        image_path: Path to the form image

    Returns:
        JSON string with field specifications
    """
    print(f"Step 1: Analyzing form image at {image_path}...")

    response = call_claude(ANALYZER_PROMPT, file_path=image_path)

    json_response = clean_json_response(response)

    print("\nField specifications extracted:")
    print(json_response)

    return json_response


def build_json_form(field_specs_json):
    """
    Generate HTML form from field specifications.

    Args:
        field_specs_json: JSON string with field specifications

    Returns:
        HTML form markup
    """
    print("\nStep 2: Building QSR Form...")

    prompt = f"{BUILDER_PROMPT}\n\nHere are the field specifications:\n\n{field_specs_json}"

    response = call_claude(prompt)

    # Clean up any markdown formatting
    html_response = clean_html_response(response)

    return html_response


def convert_form(image_path, output_path: str = None):
    """
    Convert a paper form to HTML.

    Args:
        image_path: Path to the form image
        output_path: Path to save the HTML output

    Returns:
        Generated HTML
    """
    # Step 1: Analyze the form
    field_specs = analyze_form(image_path)

    # Step 2: Build JSON form
    json_form = build_json_form(field_specs)

    # Save to file
    if output_path:
        with open(output_path, 'w') as f:
            f.write(json_form)

    print("\n" + "=" * 80)
    print("CONVERSION COMPLETE")
    print("=" * 80)
    print(f"JSON saved to: {output_path}")

    return json_form
