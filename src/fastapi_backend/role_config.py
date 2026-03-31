# Role hierarchy configuration
# Roles are ordered from lowest to highest privilege level
# A user with a higher privilege level can access data of lower levels

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
        return ROLE_HIERARCHY.index(role)
    except ValueError:
        return -1


def can_access_readings(user_role: str, required_clearance: str) -> bool:
    """
    Check if a user with given role can access readings with given clearance level.
    User can access if their privilege level >= required clearance level.
    """
    user_level = get_role_level(user_role)
    required_level = get_role_level(required_clearance)
    
    if user_level == -1 or required_level == -1:
        return False
    
    return user_level >= required_level


def can_view_sensor(user_role: str, sensor_display_clearance: str) -> bool:
    """
    Check if a user can view a sensor on the map/list.
    """
    return can_access_readings(user_role, sensor_display_clearance)
