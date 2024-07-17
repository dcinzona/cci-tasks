def stringifyListOfTuples(listOfTuples):
    """
    Converts a list of tuples to a string.
    """
    return "".join(
        ["(" + str(tup[0]) + ", " + str(tup[1]) + ") " for tup in listOfTuples]
    )


def makeInClauseFromList(listOfItems, delimiter=","):
    """
    Converts a list of items to an SQL IN clause.
    """
    if isinstance(listOfItems, str):
        listOfItems = listOfItems.split(delimiter)
    return str(tuple(listOfItems)).replace(",)", ")")
    return "(%s)" % ", ".join([f"'{str(i)}'" for i in listOfItems])
