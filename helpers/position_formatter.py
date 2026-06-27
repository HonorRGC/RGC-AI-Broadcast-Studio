class PositionFormatter:
    """
    Converts numeric race positions into natural English ordinals.

    Example:
        1  -> first
        2  -> second
        3  -> third
        4  -> fourth
        21 -> twenty-first
    """

    _ORDINALS = {
        1: "first",
        2: "second",
        3: "third",
        4: "fourth",
        5: "fifth",
        6: "sixth",
        7: "seventh",
        8: "eighth",
        9: "ninth",
        10: "tenth",
        11: "eleventh",
        12: "twelfth",
        13: "thirteenth",
        14: "fourteenth",
        15: "fifteenth",
        16: "sixteenth",
        17: "seventeenth",
        18: "eighteenth",
        19: "nineteenth",
        20: "twentieth",
        21: "twenty-first",
        22: "twenty-second",
        23: "twenty-third",
        24: "twenty-fourth",
        25: "twenty-fifth",
        26: "twenty-sixth",
        27: "twenty-seventh",
        28: "twenty-eighth",
        29: "twenty-ninth",
        30: "thirtieth",
        31: "thirty-first",
        32: "thirty-second",
        33: "thirty-third",
        34: "thirty-fourth",
        35: "thirty-fifth",
        36: "thirty-sixth",
        37: "thirty-seventh",
        38: "thirty-eighth",
        39: "thirty-ninth",
        40: "fortieth",
        41: "forty-first",
        42: "forty-second",
        43: "forty-third",
        44: "forty-fourth",
        45: "forty-fifth",
        46: "forty-sixth",
        47: "forty-seventh",
        48: "forty-eighth",
        49: "forty-ninth",
        50: "fiftieth",
    }

    @classmethod
    def ordinal(cls, position):
        """
        Returns the ordinal word for a numeric position.
        """

        try:
            position = int(position)
        except (TypeError, ValueError):
            return str(position)

        return cls._ORDINALS.get(position, f"{position}th")