"""Permissões da vertical Titan Asset & Sustainment (A4).

**Permissão, nunca papel, é o que um comando/query exige**
(`docs/asset/11_AUTHORIZATION_MODEL.md` §3; mesmo princípio de
`livestock_application.authorization`). O catálogo completo já está definido
em `docs/asset/09_COMMAND_MODEL.md`/`11_AUTHORIZATION_MODEL.md` §3, mas as
constantes só entram aqui quando o serviço correspondente existe
(constituição §38) — cresce incrementalmente por agregado, igual ao restante
de `asset_application`/`asset_infrastructure`.

`ROLE_PERMISSIONS` fica de fora deliberadamente por ora: a vertical ainda não
tem um fluxo de onboarding análogo a `EntityTypeRequest` de Livestock que
concederia um Role a partir de um pedido — inventar papéis sem esse
consumidor seria antecipar design sem uso real (constituição §38). A
atribuição papel→permissão, quando existir, é dado de seed/bootstrap, não
constante de código (mesmo argumento usado para `FRIGORIFICO`/`VETERINARIO`
em Livestock: "Role sem Permission é honesto").
"""

from typing import Final

# -- Vehicle -------------------------------------------------------------

VEHICLE_REGISTER: Final = "ASSET_VEHICLE.REGISTER"
VEHICLE_SET_BASELINE: Final = "ASSET_VEHICLE.SET_BASELINE"
VEHICLE_RECORD_METER: Final = "ASSET_VEHICLE.RECORD_METER"
VEHICLE_CORRECT_METER: Final = "ASSET_VEHICLE.CORRECT_METER"
VEHICLE_TRANSITION: Final = "ASSET_VEHICLE.TRANSITION"
VEHICLE_READ: Final = "ASSET_VEHICLE.READ"


# -- Part / InterchangeabilityGroup ---------------------------------------

PART_REGISTER: Final = "ASSET_PART.REGISTER"
PART_ADD_REVISION: Final = "ASSET_PART.ADD_REVISION"
PART_SUPERSEDE: Final = "ASSET_PART.SUPERSEDE"
PART_EDIT_INTERCHANGE: Final = "ASSET_PART.EDIT_INTERCHANGE"
PART_READ: Final = "ASSET_PART.READ"

# -- Applicability ---------------------------------------------------------

APPLICABILITY_ASSERT: Final = "ASSET_APPLICABILITY.ASSERT"
APPLICABILITY_WITHDRAW: Final = "ASSET_APPLICABILITY.WITHDRAW"
APPLICABILITY_READ: Final = "ASSET_APPLICABILITY.READ"

# -- Configuration -----------------------------------------------------------

CONFIG_PUBLISH: Final = "ASSET_CONFIG.PUBLISH"
CONFIG_SUPERSEDE: Final = "ASSET_CONFIG.SUPERSEDE"
CONFIG_READ: Final = "ASSET_CONFIG.READ"

# -- CustomerSite --------------------------------------------------------

SITE_REGISTER: Final = "ASSET_SITE.REGISTER"
SITE_READ: Final = "ASSET_SITE.READ"

# -- Inventory ---------------------------------------------------------------

INVENTORY_OPEN_POSITION: Final = "ASSET_INVENTORY.OPEN_POSITION"
INVENTORY_ADJUST: Final = "ASSET_INVENTORY.ADJUST"
INVENTORY_RESERVE: Final = "ASSET_INVENTORY.RESERVE"
INVENTORY_RELEASE: Final = "ASSET_INVENTORY.RELEASE"
INVENTORY_ALLOCATE: Final = "ASSET_INVENTORY.ALLOCATE"
INVENTORY_CONSUME: Final = "ASSET_INVENTORY.CONSUME"
INVENTORY_TRANSFER_REQUEST: Final = "ASSET_INVENTORY.TRANSFER_REQUEST"
INVENTORY_TRANSFER_DISPATCH: Final = "ASSET_INVENTORY.TRANSFER_DISPATCH"
INVENTORY_TRANSFER_RECEIVE: Final = "ASSET_INVENTORY.TRANSFER_RECEIVE"
INVENTORY_READ: Final = "ASSET_INVENTORY.READ"

LEITURA: Final = frozenset(
    {VEHICLE_READ, PART_READ, APPLICABILITY_READ, CONFIG_READ, SITE_READ, INVENTORY_READ}
)

ESCRITA: Final = frozenset(
    {
        VEHICLE_REGISTER,
        VEHICLE_SET_BASELINE,
        VEHICLE_RECORD_METER,
        VEHICLE_CORRECT_METER,
        VEHICLE_TRANSITION,
        PART_REGISTER,
        PART_ADD_REVISION,
        PART_SUPERSEDE,
        PART_EDIT_INTERCHANGE,
        APPLICABILITY_ASSERT,
        APPLICABILITY_WITHDRAW,
        CONFIG_PUBLISH,
        CONFIG_SUPERSEDE,
        SITE_REGISTER,
        INVENTORY_OPEN_POSITION,
        INVENTORY_ADJUST,
        INVENTORY_RESERVE,
        INVENTORY_RELEASE,
        INVENTORY_ALLOCATE,
        INVENTORY_CONSUME,
        INVENTORY_TRANSFER_REQUEST,
        INVENTORY_TRANSFER_DISPATCH,
        INVENTORY_TRANSFER_RECEIVE,
    }
)

ASSET_PERMISSIONS: Final = LEITURA | ESCRITA
