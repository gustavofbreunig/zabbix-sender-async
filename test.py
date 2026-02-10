import asyncio

from zabbixasync.sender import AsyncSender, ItemData

ZABBIX_SERVER = "127.0.0.1"  # update if needed
ZABBIX_PORT = 10051
ZABBIX_HOST = "sender-test"
PSK_IDENTITY = "sender-test-psk"
PSK_HEX = "00112233445566778899AABBCCDDEEFF"
LONG_TEXT_VALUE = (
    "This is a long trapper text payload used to verify sender behavior with "
    "bigger string values in Zabbix. "
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
    "veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea "
    "commodo consequat."
)


async def main() -> None:
    sender = AsyncSender(
        ZABBIX_SERVER,
        ZABBIX_PORT,
        tls_connect="psk",
        tls_psk_identity=PSK_IDENTITY,
        tls_psk=PSK_HEX,
    )
    items = [
        ItemData(
            host=ZABBIX_HOST,
            key="test.trapper.int",
            value=42,
        ),
        ItemData(
            host=ZABBIX_HOST,
            key="test.trapper.text",
            value=LONG_TEXT_VALUE,
        ),
    ]
    result = await sender.send(items)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
