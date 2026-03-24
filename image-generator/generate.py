import sys, os, requests, base64, argparse
from openai import OpenAI

def main():
    parser = argparse.ArgumentParser(description="Generate and evaluate an image using OpenAI.")
    parser.add_argument("prompt", help="The prompt for the image generation")
    parser.add_argument("folder", help="Target destination folder")
    parser.add_argument("criteria", help="Criteria for evaluation")
    parser.add_argument("--model", default="dall-e-3", help="Image generation model to use")
    parser.add_argument("--size", default="1024x1024", help="Size of the image")
    parser.add_argument("--quality", default="standard", help="Quality of the image")
    parser.add_argument("--moderation", default="low", help="Moderation setting")
    parser.add_argument("--background", default="opaque", help="Background setting")
    parser.add_argument("--output-format", default="png", dest="output_format")
    parser.add_argument("--poll-interval", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--vision-model", default="gpt-4o", dest="vision_model")
    
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is missing.", file=sys.stderr)
        print("Please ensure your API key is set in the environment or await the next Windows restart if previously set.", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    print(f"Generating image with model '{args.model}'...")
    try:
        response = client.images.generate(
            model=args.model,
            prompt=f"Create an image matching this request: {args.prompt}. Ensure it strictly follows these criteria: {args.criteria}",
            n=1,
            size=args.size
        )
    except Exception as e:
        print(f"Generation failed: {e}", file=sys.stderr)
        sys.exit(1)

    image_url = response.data[0].url
    print(f"Image generated! Downloading from {image_url}...")
    
    try:
        image_data = requests.get(image_url, timeout=args.timeout).content
    except Exception as e:
        print(f"Downloading image failed: {e}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.folder, exist_ok=True)
    image_path = os.path.join(args.folder, f"generated_image.{args.output_format}")

    with open(image_path, "wb") as f:
        f.write(image_data)

    print(f"Evaluating image using '{args.vision_model}' against criteria: '{args.criteria}'")
    base64_image = base64.b64encode(image_data).decode('utf-8')
    try:
        vision_eval = client.chat.completions.create(
            model=args.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Analyze this image. Does it strictly meet the following design criteria: '{args.criteria}'? Reply ONLY with 'YES' or 'NO: [Reason]'."},
                        {"type": "image_url", "image_url": {"url": f"data:image/{args.output_format};base64,{base64_image}"}}
                    ]
                }
            ]
        )
        evaluation = vision_eval.choices[0].message.content
    except Exception as e:
        print(f"Evaluation request failed: {e}", file=sys.stderr)
        sys.exit(1)

    if evaluation.startswith("NO"):
        print(f"Design mismatch: {evaluation}")
        sys.exit(1)

    print(f"Success! Image saved to {image_path}")

if __name__ == "__main__":
    main()
