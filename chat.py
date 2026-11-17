#!/usr/bin/env python3
"""
AgentSUMO CLI Chat Interface

Allows direct conversation with AgentSUMO.
"""

import asyncio
import sys
import argparse
from pathlib import Path

from dotenv import load_dotenv

# Load the .env next to this script before anything reads the environment.
# python-dotenv strips quotes and inline comments, and variables already set
# in the shell take precedence. A legacy claude_api.txt is still read by
# AgentSUMOConfig when ANTHROPIC_API_KEY is not set.
load_dotenv(Path(__file__).parent / ".env")

from agentsumo import AgentSUMO


async def main(debug=False):
    """
    Start the CLI chat.

    Args:
        debug: Debug mode (shows Claude raw responses)
    """
    print("\n" + "="*70)
    print("AgentSUMO - AI-Powered SUMO Simulation Platform")
    if debug:
        print("    DEBUG MODE: Raw responses visible")
    print("="*70)
    print("\nInitializing...")

    try:
        async with AgentSUMO(enable_debug=debug) as agent:
            print("\nAgentSUMO is ready.")
            print("\nCommands.")
            print("  - 'quit' or 'exit' to quit")
            print("  - 'state' to check current state")
            print("  - 'reset' to reset conversation history")
            print("  - 'help' to show help")
            print("\nTip.")
            print("  - <thinking> tag for Claude's reasoning process (Complex tasks)")
            print("  - <extended_thinking> tag for Claude's deep exploration (Agentic tasks)")
            print("="*70 + "\n")

            while True:
                try:
                    # User input
                    user_input = input("\nYou: ").strip()

                    if not user_input:
                        continue

                    # Exit command
                    if user_input.lower() in ['quit', 'exit', 'q', 'bye']:
                        print("\nExiting AgentSUMO.\n")
                        break

                    # State check
                    if user_input.lower() == 'state':
                        state = agent.get_state()
                        print("\nCurrent state.")
                        print(f"   Network: {state['simulation_state']['current_network'] or 'None'}")
                        print(f"   Routes: {state['simulation_state']['current_routes'] or 'None'}")
                        print(f"   Conversation turns: {state['conversation_turns']}")
                        print(f"   Tools available: {state['tools_available']}")
                        continue

                    # Reset conversation
                    if user_input.lower() == 'reset':
                        agent.reset_conversation()
                        print("\nConversation history has been reset.")
                        continue

                    # Help
                    if user_input.lower() == 'help':
                        print("\nUsage examples.")
                        print("  - 'Hello!'")
                        print("  - 'What is SUMO?'")
                        print("  - 'Please create a network for 강남역'")
                        print("  - 'What tools are available?'")
                        print("  - 'Please analyze the average travel time'")
                        continue

                    # Chat with AgentSUMO
                    print()
                    response = await agent.chat(user_input)
                    print(f"\nAgentSUMO.")
                    print("-" * 70)
                    print(response)
                    print("-" * 70)

                except KeyboardInterrupt:
                    print("\n\nCtrl+C detected. Type 'quit' to exit.\n")
                    continue

                except EOFError:
                    print("\n\nExiting AgentSUMO.\n")
                    break

                except Exception as e:
                    print(f"\nError occurred. {e}")
                    print("You can continue the conversation.\n")

    except KeyboardInterrupt:
        print("\n\nExiting AgentSUMO.\n")
        sys.exit(0)

    except Exception as e:
        print(f"\nInitialization failed. {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Argument parsing
    parser = argparse.ArgumentParser(description='AgentSUMO CLI')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode (show raw Claude responses)')
    args = parser.parse_args()

    print("\nStarting AgentSUMO CLI...\n")
    try:
        asyncio.run(main(debug=args.debug))
    except KeyboardInterrupt:
        print("\n\nExited.\n")
        sys.exit(0)
