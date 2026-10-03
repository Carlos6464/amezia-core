class CategoryNotFoundError(Exception):
    pass


class CategoryNotEditableError(Exception):
    pass


class DuplicateCategoryNameError(Exception):
    pass


class CategoryInUseError(Exception):
    pass
