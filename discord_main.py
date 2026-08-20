from griffin.discord_bridge import DiscordBridgeError, run_discord_bridge

if __name__ == "__main__":
    try:
        run_discord_bridge()
    except DiscordBridgeError as exc:
        print(f"[can't start Discord bridge: {exc}]")
