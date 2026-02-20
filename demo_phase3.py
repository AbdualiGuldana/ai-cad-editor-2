"""
Jsut demo
Interactive chat with your DXF file using OpenAI GPT-4.
Requirements:
    pip install openai
Usage:
    export OPENAI_API_KEY="your-api-key"
    python demo_phase3.py
"""

import os
import sys
from ai_cad_editor.agent import CADAgentOpenAI

DXF_FILE = "examples/dxf_files/building005-0_floor2.dxf"


def main():
    print("Demo")

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\nError: OPENAI_API_KEY not set")
        print("Run: export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)

    print(f"\nLoading: {DXF_FILE}")

    try:
        agent = CADAgentOpenAI(DXF_FILE)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    while True:
        try:
            print()
            user_input = input("Request: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ('quit', 'exit', 'q'):
                print("End!")
                break

            if user_input.lower() == 'reset':
                agent.reset()
                print("Conversation reset.")
                continue

            response = agent.chat(user_input)
            print(f"\nAI: {response}")

        except KeyboardInterrupt:
            print("\nEnd!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
