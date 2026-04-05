# Role hierarchy configuration
# Roles are ordered from lowest to highest privilege level
# A user with a higher privilege level can access data of lower levels

import logging

logger = logging.getLogger(__name__)

ROLE_HIERARCHY = [
    "guest",           # No data access, can only see public information
    "regular",         # Can access regular clearance sensors
    "elevated",        # Can access elevated clearance sensors
    "full_clearance",  # Can access full clearance sensors
    "top_secret"       # Can access top secret sensors
]

# Default clearance levels for sensors
DEFAULT_READINGS_CLEARANCE = "regular"
DEFAULT_DISPLAY_CLEARANCE = "regular"

# Default role for new users
DEFAULT_USER_ROLE = "regular"


def get_role_level(role: str) -> int:
    """
    Get the numeric level of a role.
    Higher number = higher privilege.
    Returns -1 if role is not found.
    """
    try:
        level = ROLE_HIERARCHY.index(role)
        logger.debug(f"Role '{role}' has privilege level {level}")
        return level
    except ValueError:
        logger.warning(f"Invalid role '{role}' - not found in hierarchy")
        return -1


def can_access_readings(user_role: str, required_clearance: str) -> bool:
    """
    Check if a user with given role can access readings with given clearance level.
    User can access if their privilege level >= required clearance level.
    """
    user_level = get_role_level(user_role)
    required_level = get_role_level(required_clearance)
    
    if user_level == -1:
        logger.warning(f"Access check failed: invalid user role '{user_role}'")
        return False
    
    if required_level == -1:
        logger.warning(f"Access check failed: invalid clearance level '{required_clearance}'")
        return False
    
    can_access = user_level >= required_level
    
    if can_access:
        logger.debug(f"Access GRANTED: user role '{user_role}' (level {user_level}) >= required clearance '{required_clearance}' (level {required_level})")
    else:
        logger.debug(f"Access DENIED: user role '{user_role}' (level {user_level}) < required clearance '{required_clearance}' (level {required_level})")
    
    return can_access


def can_view_sensor(user_role: str, sensor_display_clearance: str) -> bool:
    """
    Check if a user can view a sensor on the map/list.
    """
    can_view = can_access_readings(user_role, sensor_display_clearance)
    if can_view:
        logger.debug(f"Sensor visibility GRANTED: user role '{user_role}' can view sensor with display_clearance '{sensor_display_clearance}'")
    else:
        logger.debug(f"Sensor visibility DENIED: user role '{user_role}' cannot view sensor with display_clearance '{sensor_display_clearance}'")
    return can_view
