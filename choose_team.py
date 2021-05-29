import pandas as pd
import pyomo.environ as pyomo_env
from pyomo.opt import SolverFactory
from prettytable import PrettyTable

from common import Position


def create_model(dataframe):
    model = pyomo_env.ConcreteModel()

    model.name_ = pyomo_env.Set(initialize=dataframe.name_.to_list())
    model.cost_ingame = pyomo_env.Param(
        model.name_,
        initialize=dict(zip(dataframe.name_, dataframe.cost_ingame)),
        within=pyomo_env.NonNegativeReals,
    )
    model.market_value = pyomo_env.Param(
        model.name_, initialize=dict(zip(dataframe.name_, dataframe.market_value))
    )
    model.position = pyomo_env.Param(
        model.name_, initialize=dict(zip(dataframe.name_, dataframe.position))
    )

    # Is the player chosen for the final team?
    model.Chosen = pyomo_env.Var(model.name_, within=pyomo_env.Boolean, initialize=1)
    model.max_nation_count = pyomo_env.Var(within=pyomo_env.Integers, initialize=0)

    # Maximize the market value of the players.
    def market_value_rule(model):
        market_value_sum = sum(
            model.market_value[i] * model.Chosen[i] for i in model.name_
        )
        return market_value_sum  # negate to maximize

    model.average_market_value = pyomo_env.Objective(
        rule=market_value_rule, sense=pyomo_env.maximize
    )

    # Constrain the cost of the players.
    def cost_rule(model):
        value = sum(model.cost_ingame[i] * model.Chosen[i] for i in model.name_)
        return value <= 100 * 10 ** 6  # Maximum 10 Mio.

    model.total_cost = pyomo_env.Constraint(model.name_, rule=cost_rule)

    # Constrain the amount of players for each position.
    def goalkeeper_rule(model):
        value = sum(
            model.Chosen[i] * (model.position[i] == Position.GOALKEEPER.value)
            for i in model.name_
        )
        return pyomo_env.inequality(2, value, 2)

    model.goalkeeper = pyomo_env.Constraint(model.name_, rule=goalkeeper_rule)

    def defense_rule(model):
        value = sum(
            model.Chosen[i] * (model.position[i] == Position.DEFENSE.value)
            for i in model.name_
        )
        return pyomo_env.inequality(5, value, 5)

    model.defense = pyomo_env.Constraint(model.name_, rule=defense_rule)

    def midfield_rule(model):
        value = sum(
            model.Chosen[i] * (model.position[i] == Position.MIDFIELD.value)
            for i in model.name_
        )
        return pyomo_env.inequality(5, value, 5)

    model.midfield = pyomo_env.Constraint(model.name_, rule=midfield_rule)

    def offense_rule(model):
        value = sum(
            model.Chosen[i] * int(model.position[i] == Position.OFFENSE.value)
            for i in model.name_
        )
        return pyomo_env.inequality(3, value, 3)

    model.offense = pyomo_env.Constraint(model.name_, rule=offense_rule)

    # Team has to be exactly 15 players in total.
    def total_players_rule(model):
        value = sum(model.Chosen[i] for i in model.name_)
        return value == 15

    model.total_players = pyomo_env.Constraint(model.name_, rule=total_players_rule)

    return model


def print_results(model):
    total_ingame_sum = 0
    total_market_value = 0
    team = []
    for i in model.name_:
        if bool(pyomo_env.value(model.Chosen[i])):
            team.append(
                (
                    Position(model.position[i]),
                    i,
                    model.cost_ingame[i] / 1000000.0,
                    model.market_value[i] / 1000000.0,
                    f"{model.market_value[i] / model.cost_ingame[i]:.2f}",
                )
            )
            total_ingame_sum += model.cost_ingame[i]
            total_market_value += model.market_value[i]

    table = PrettyTable()
    table.field_names = [
        "Position",
        "Name",
        "Ingame value [Mio. €]",
        "Market value [Mio. €]",
        "Ratio (ingame / market)",
    ]
    for player in sorted(team):
        table.add_row(player)
    table.add_row(
        (
            "-",
            "Total",
            total_ingame_sum / 1000000.0,
            total_market_value / 1000000.0,
            f"{total_market_value / total_ingame_sum:.2f}",
        )
    )
    print(table)


def main():
    dataframe = pd.read_csv("work/test.csv")
    model = create_model(dataframe)

    opt = SolverFactory("glpk")
    opt.solve(model)

    print_results(model)


if __name__ == "__main__":
    main()
