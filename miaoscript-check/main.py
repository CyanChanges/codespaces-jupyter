import logging
import asyncio
from typing import Sequence, Any

from aiohttp import ClientSession, ClientResponseError
from rich import print
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
PluginInfo = Any

NPM_REGISTRY_ENDPOINT = 'https://registry.npmjs.org/'
SEARCH_REGISTRY_ENDPOINT = 'https://registry.koishi.chat/'

async def check_if_dep(session: ClientSession, package_name: str, plugins: Sequence[PluginInfo], targets: Sequence[PluginInfo]) -> bool:
    async with session.get(f'/{package_name}') as r1:
                try:
                    r1.raise_for_status()
                except ClientResponseError:
                    return False

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
                    return True
                
    return False



async def scan_deps(package_names: Sequence[str], plugins: Sequence[PluginInfo], targets: Sequence[PluginInfo]) -> Sequence[PluginInfo]:
    async with ClientSession(NPM_REGISTRY_ENDPOINT, headers=headers) as session:
        filter_coro = map(lambda name: check_if_dep(session, name, plugins, targets), package_names)

        filterer = await asyncio.gather(*filter_coro)

        return tuple(filter(lambda idx_plugin: filterer[idx_plugin[0]], enumerate(plugins)))

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

    for idx, name in enumerate(short_names):
        if 'miao' in name or plugins[idx]['package']['publisher']['email'] == 'admin@yumc.pw':
            matches_pub.append(plugins[idx])
    
    
    matches_by_deps = await scan_deps([name for name in tuple(map(lambda p: p['package']['name'], plugins))], plugins, matches_pub)    

    return matches_pub, matches_by_deps if matches_by_deps else []

def print_package(pkg_info):
    print(
        f"{pkg_info['shortname']} | "
        f"{pkg_info['package']['publisher']['username']} | "
        f"{pkg_info['package']['version']}" 
    )

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    m_pub, m_by_dep = loop.run_until_complete(scan_once())

    [print_package(match) for match in m_pub]
    [print_package(match) for match in m_by_dep]

    logger.debug(m_pub)
    logger.debug(m_by_dep)
    
    logger.info("[green]complete", extra={"markup": True})

if __name__ == '__main__':
     main()
