import time
import logging
import asyncio
from typing import Sequence, Any

from aiohttp import ClientSession, ClientResponseError
from rich import print
from rich.pretty import pprint
from rich.logging import RichHandler
from rich.console import Console
from rich.traceback import install

console = Console()

install(console=console)

FORMAT = "%(message)s"
logging.basicConfig(
    level="INFO", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
)

logger = logging.getLogger("checker")

headers = {"content-type": "application/json"}

PackageInfo = Any

NPM_REGISTRY_ENDPOINT = 'https://registry.npmjs.org/'
SEARCH_REGISTRY_ENDPOINT = 'https://registry.koishi.chat/'

async def scan_deps(package_names: Sequence[str], plugins: Sequence[PackageInfo], targets: Sequence[PackageInfo]) -> Sequence[PackageInfo]:
    result = []
    async with ClientSession(NPM_REGISTRY_ENDPOINT, headers=headers) as session:
        for idx, name in enumerate(package_names):
            async with session.get(f"/{plugins[idx]['package']['name']}") as r1:
                try:
                    r1.raise_for_status()
                except ClientResponseError:
                    continue

                package_info = await r1.json()

                latest_version = package_info['dist-tags']['latest']

                latest_package_json = package_info['versions'][latest_version]
                latest_peer_deps = latest_package_json.get('peerDependencies', {})
                latest_deps = latest_package_json.get('dependencies', {})

                depend_with_peer_deps = any(
                    match['package']['name'] in latest_peer_deps.keys()
                    for match in targets
                )

                depend_with_deps = any(
                    match['package']['name'] in latest_deps.keys()
                    for match in targets
                )

                if depend_with_deps or depend_with_peer_deps:
                    result.append(plugins[idx])

    return result

async def scan_once():
    result = None

    async with ClientSession(SEARCH_REGISTRY_ENDPOINT, headers=headers) as ss:
        async with ss.get('/', compress=True) as r:
            try:
                r.raise_for_status()
            except ClientResponseError:
                logger.warning(await r.text())
                raise

            result = await r.json()

    assert result

    plugins = result['objects']
    short_names = tuple(map(lambda p: p['shortname'], plugins))

    matches_pub = []
    matches_by_dep = []

    for idx, name in enumerate(short_names):
        if 'miao' in name or plugins[idx]['package']['publisher']['email'] == 'admin@yumc.pw':
            matches_pub.append(plugins[idx])
    
    await scan_deps([name for name in tuple(map(lambda p: p['package']['name'], plugins))], plugins, matches_pub)

    
    return matches_pub, matches_by_dep

def print_package(pkg_info):
    print(f"{pkg_info['shortname']} | "
          f"{pkg_info['package']['publisher']['username']} | "
          f"{pkg_info['package']['version']}" 
    )

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for _ in range(0, 15):
        m_pub, m_by_dep = loop.run_until_complete(scan_once())

        map(print_package, (match for match in m_pub))

        logger.debug(m_pub)

        logger.info("[green]complete", extra={"markup": True})

        time.sleep(90)
