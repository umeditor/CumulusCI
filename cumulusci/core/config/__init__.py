# IMPORT ORDER MATTERS!

# constants used by MetaCI
FAILED_TO_CREATE_SCRATCH_ORG = "Failed to create scratch org"

from cumulusci.core.config.BaseConfig import BaseConfig

# inherit from BaseConfig


class ConnectedAppOAuthConfig(BaseConfig):
    """ Salesforce Connected App OAuth configuration """

    pass


class FlowConfig(BaseConfig):
    """ A flow with its configuration merged """

    pass


from cumulusci.core.config.OrgConfig import OrgConfig  # noqa: F401


class ServiceConfig(BaseConfig):
    pass


class TaskConfig(BaseConfig):
    """ A task with its configuration merged """

    pass


from cumulusci.core.config.BaseTaskFlowConfig import BaseTaskFlowConfig  # noqa: F401


# inherit from BaseTaskFlowConfig
from cumulusci.core.config.BaseProjectConfig import BaseProjectConfig  # noqa: F401

# inherit from OrgConfig
from cumulusci.core.config.ScratchOrgConfig import ScratchOrgConfig  # noqa: F401

# inherit from BaseProjectConfig
from cumulusci.core.config.BaseGlobalConfig import BaseGlobalConfig  # noqa: F401
