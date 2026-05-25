from src.agents.chat_agent import ChatAgent


def main():
    print("Drone Flight Suitability Assistant")
    print("Ask me whether conditions are suitable for a drone flight at a given location and time.")
    print("Type 'exit' to quit.")
    print()

    agent = ChatAgent()

    while True:
        try:
            user_input = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGörüşürüz.")
            break

        if not user_input:
            continue

        if agent.is_exit_command(user_input):
            print("Görüşürüz.")
            break

        print()
        print("Analyzing, please wait...")
        print()

        response = agent.chat(user_input)
        print(response)
        print()


if __name__ == "__main__":
    main()
