"""Composicao minima de handlers do worker para o fluxo LIV-C09."""

from dataclasses import dataclass

from packages.core_application import IncomingMessageEnvelope, MessageHandler
from packages.livestock_application.erp_inbox import (
    LivestockErpInboxHandler,
    NeutralOperationalIntentSimulatorAdapter,
)


@dataclass(frozen=True, slots=True)
class WorkerHandlerRegistry:
    livestock_handler: LivestockErpInboxHandler

    @classmethod
    def default(cls) -> "WorkerHandlerRegistry":
        return cls(
            livestock_handler=LivestockErpInboxHandler(
                delivery=NeutralOperationalIntentSimulatorAdapter()
            )
        )

    def resolve(self, envelope: IncomingMessageEnvelope) -> MessageHandler:
        return self.livestock_handler
