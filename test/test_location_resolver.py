from src.agents.location_resolver_agent import LocationResolverAgent


def main():
    agent = LocationResolverAgent()

    result = agent.resolve("Riga National Library")

    print("LocationResolverAgent result:")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
