"""The only initialization path used by desktop, CLI and API."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from treecut.config import Settings, load_settings
from treecut.models.policy import ModelPlan, select_model_plan
from treecut.platform.capabilities import Capabilities, detect_capabilities
from treecut.platform.logging import configure_logging
from treecut.platform.paths import RuntimePaths
from treecut.extensions import load_extensions


@dataclass(frozen=True)
class AppContext:
    paths: RuntimePaths
    settings: Settings
    capabilities: Capabilities
    model_plan: ModelPlan
    logger: logging.Logger
    domain_vocabulary: tuple[str, ...] = ()


def bootstrap(verbose: bool = False) -> AppContext:
    paths = RuntimePaths.discover()
    paths.apply_environment()
    logger = configure_logging(paths, verbose=verbose)
    settings = load_settings(paths)
    capabilities = detect_capabilities(paths)
    model_plan = select_model_plan(capabilities, settings.model_mode, settings.vision_mode)
    load_extensions(paths.data_root)
    from treecut.knowledge import domain_vocabulary
    domain_terms = domain_vocabulary(paths.install_root)
    logger.info(
        "TreeCut v13 initialized: profile=%s vision=%s speech=%s data=%s",
        model_plan.profile, model_plan.vision, model_plan.speech, paths.data_root,
    )
    return AppContext(paths, settings, capabilities, model_plan, logger, domain_terms)
