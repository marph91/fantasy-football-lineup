import argparse

import pandas as pd
import pyomo.environ as pyomo_env
from pyomo.opt import SolverFactory
from prettytable import PrettyTable

from common import Position


def create_model(dataframe):
    # Configuration
    expected_position_counts = {
        Position.GOALKEEPER: 2,
        Position.DEFENDER: 4,
        Position.MIDFIELDER: 6,
        Position.FORWARD: 3,
    }
    total_players = 15
    players_per_nation = (0, 3)  # minimum 0, maximum 3
    maximum_ingame_value = 30.0 * 10**6  # million

    # Define the actual model.
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
    model.nationality = pyomo_env.Param(
        model.name_,
        initialize=dict(zip(dataframe.name_, dataframe.nationality)),
        within=pyomo_env.Any,
    )
    model.position = pyomo_env.Param(
        model.name_, initialize=dict(zip(dataframe.name_, dataframe.position))
    )

    # Is the player chosen for the final team?
    model.chosen = pyomo_env.Var(model.name_, within=pyomo_env.Boolean, initialize=1)

    # Objective: Maximize the market value of the players.
    def market_value_rule(model):
        market_value_sum = sum(
            model.market_value[i] * model.chosen[i] for i in model.name_
        )
        return market_value_sum

    model.average_market_value = pyomo_env.Objective(
        rule=market_value_rule, sense=pyomo_env.maximize
    )

    # Constraint: Ingame cost of the players.
    def cost_rule(model):
        value = sum(model.cost_ingame[i] * model.chosen[i] for i in model.name_)
        return value <= maximum_ingame_value

    model.total_cost = pyomo_env.Constraint(rule=cost_rule)

    # Constraint: Amount of players for each position.
    def position_rule(model, position, expected_count):
        actual_count = sum(
            model.chosen[i] * (model.position[i] == position.name) for i in model.name_
        )
        return actual_count == expected_count

    model.positions = pyomo_env.Constraint(
        expected_position_counts.items(), rule=position_rule
    )

    # Constraint: Maximum team size.
    def total_players_rule(model):
        value = sum(model.chosen[i] for i in model.name_)
        return value == total_players

    model.total_players = pyomo_env.Constraint(rule=total_players_rule)

    # Constraint: Amount of players of each national team.
    def nationality_rule(model, nation, count_min, count_max):
        actual_count = sum(
            model.chosen[i] * (model.nationality[i] == nation) for i in model.name_
        )
        return pyomo_env.inequality(count_min, actual_count, count_max)

    expected_nation_counts = {
        nation: players_per_nation for nation in set(dataframe.nationality.to_list())
    }
    model.nationalities = pyomo_env.Constraint(
        expected_nation_counts.items(), rule=nationality_rule
    )

    return model


def print_results(model):
    total_ingame_sum = 0
    total_market_value = 0
    team = []
    for i in model.name_:
        if bool(pyomo_env.value(model.chosen[i])):
            team.append(
                (
                    Position[model.position[i]],
                    i,
                    model.cost_ingame[i] / 1000000.0,
                    model.market_value[i],
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
        "Ratio (market / ingame)",
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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force", action="store_true", help="Force refreshing of the cache."
    )
    parser.add_argument(
        "--show-top-ratios",
        action="store_true",
        help="Show players with the baes ratio (market value / ingame value).",
    )
    parser.add_argument(
        "--exclude-list",
        default=None,
        help="List of players to exclude. Separated by new line.",
    )
    args = parser.parse_args()

    dataframe = pd.read_csv("work/test.csv")

    if args.exclude_list is not None:
        with open(args.exclude_list) as infile:
            exclude_list = infile.readlines()
        dataframe = dataframe[~dataframe["name_"].isin(exclude_list)]

    model = create_model(dataframe)

    opt = SolverFactory("glpk")
    opt.solve(model)

    print_results(model)


if __name__ == "__main__":
    main()
