# Official Indian States & UTs (title case)
VALID_INDIAN_STATES = {
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    "Delhi",
    "Jammu And Kashmir",
    "Ladakh",
    "Chandigarh",
    "Puducherry",
    "Andaman And Nicobar Islands",
    "Dadra And Nagar Haveli And Daman And Diu",
    "Lakshadweep",
}


# City → State mapping (expand gradually as needed)
CITY_STATE_MAP = {
    # Karnataka
    "bangalore": "Karnataka",
    "bengaluru": "Karnataka",
    "mysore": "Karnataka",
    "mangalore": "Karnataka",

     # Border states
    "mumbai": "Maharashtra",
    "pune": "Maharashtra",
    "hyderabad": "Telangana",
    "chennai": "Tamil Nadu",
    "kochi": "Kerala",
    "vijayawada": "Andhra Pradesh",
}



def normalize_text(value: str | None) -> str | None:
    """
    Normalize text to title case after trimming whitespace.
    Safe for None.
    """
    if not value:
        return None
    return value.strip().title()


def is_valid_indian_state(state: str | None) -> bool:
    """
    Validate if given state is an official Indian state/UT.
    """
    if not state:
        return False

    normalized = normalize_text(state)
    return normalized in VALID_INDIAN_STATES


def infer_state_from_address(address: str | None) -> str | None:
    """
    Extract state from address by scanning for known cities.

    Production-safe:
    - Case insensitive
    - Trim safe
    - Substring match
    - Deterministic return
    """
    if not address:
        return None

    address_lower = address.strip().lower()

    for city, state in CITY_STATE_MAP.items():
        if city in address_lower:
            return state

    return None