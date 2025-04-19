def get_version() -> str:
    """
    Returns the version details of Mirror Beast.

    :return: The version details in the format 'vMAJOR.MINOR.PATCH-STATE'
    :rtype: str
    """
    MAJOR = "1"
    MINOR = "0"
    PATCH = "0"
    STATE = "beast"
    return f"v{MAJOR}.{MINOR}.{PATCH}-{STATE}"


if __name__ == "__main__":
    print(get_version())
