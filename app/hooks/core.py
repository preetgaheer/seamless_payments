class Condition:
    """Base class for conditions that support AND, OR, and NOT operators."""

    def __init__(self, name):
        self.name = name

    def __and__(self, other):
        """Overload `&` to return an AndCondition"""
        return AndCondition(self, other)

    def __or__(self, other):
        """Overload `|` to return an OrCondition"""
        return OrCondition(self, other)

    def __invert__(self):
        """Overload `~` to return a NotCondition"""
        return NotCondition(self)

    def evaluate(self, context=None):
        """Override in subclasses to provide actual logic."""
        raise NotImplementedError

    def __repr__(self):
        return self.name


class AndCondition(Condition):
    """Handles AND (`&`) logic between two conditions."""

    def __init__(self, left, right):
        self.left = left
        self.right = right

    def evaluate(self, context=None):
        return self.left.evaluate(context) and self.right.evaluate(context)

    def __repr__(self):
        return f"({self.left} & {self.right})"


class OrCondition(Condition):
    """Handles OR (`|`) logic between two conditions."""

    def __init__(self, left, right):
        self.left = left
        self.right = right

    def evaluate(self, context=None):
        return self.left.evaluate(context) or self.right.evaluate(context)

    def __repr__(self):
        return f"({self.left} | {self.right})"


class NotCondition(Condition):
    """Handles NOT (`~`) logic for a single condition."""

    def __init__(self, condition):
        self.condition = condition

    def evaluate(self, context=None):
        return not self.condition.evaluate(context)

    def __repr__(self):
        return f"~({self.condition})"


# User-related condition class
class UserCondition(Condition):
    """Condition that checks user authentication and roles."""

    def __init__(self, name, check_function):
        super().__init__(name)
        self.check_function = check_function  # A function that checks the user

    def evaluate(self, user):
        return self.check_function(user)


# Example user role check functions
def is_authenticated(user):
    return user.get("authenticated", False)


def is_admin(user):
    return user.get("role") == "admin"


def is_customer(user):
    return user.get("role") == "customer"


def is_cashier(user):
    return user.get("role") == "cashier"


# Defining conditions
IsAuthenticated = UserCondition("IsAuthenticated", is_authenticated)
IsAdmin = UserCondition("IsAdmin", is_admin)
IsCustomer = UserCondition("IsCustomer", is_customer)
IsCashier = UserCondition("IsCashier", is_cashier)


# Example Usage
if __name__ == "__main__":
    # Sample user data
    user_data = {"authenticated": True, "role": "customer"}

    # DRF-style condition definition
    permission = (IsAuthenticated & IsCustomer) | IsCashier

    print("Condition Expression:", permission)
    print("Condition Evaluation:", permission.evaluate(user_data))  # True

    # Testing a NOT condition
    permission = ~IsAdmin  # User should NOT be an Admin
    print("\nCondition Expression:", permission)
    print("Condition Evaluation:", permission.evaluate(user_data))  # True
