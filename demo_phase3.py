import os
import sys

DXF_FILE = "/Users/guldana/ai-cad-editor-2/examples/dxf_files_korean/등록428_서울 구 용산철도병원 본관_06-지하평면도.dxf"


def main():
    print("Demo")
    print()
    print("Choose AI provider:")
    print("1. OpenAI (gpt-4o)")
    print("2. Gemini (gemini-2.5-flash)")
    print()

    choice = input("Enter 1 or 2: ").strip()

    if choice == "1":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("\nError: OPENAI_API_KEY not set")
            print("Run: export OPENAI_API_KEY='your-api-key'")
            sys.exit(1)
        from ai_cad_editor.agent.cad_agent_openai import CADAgentOpenAI
        agent = CADAgentOpenAI(DXF_FILE)

    elif choice == "2":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("\nError: GEMINI_API_KEY not set")
            print("Run: export GEMINI_API_KEY='your-api-key'")
            print("Get a key at: https://aistudio.google.com/app/apikey")
            sys.exit(1)
        from ai_cad_editor.agent.cad_agent_gemini import CADAgentGemini
        agent = CADAgentGemini(DXF_FILE)

    else:
        print("Invalid choice. Enter 1 or 2.")
        sys.exit(1)

    print(f"\nLoading: {DXF_FILE}")

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
