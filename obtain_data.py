import argparse
import logging
import os
import pickle

from bs4 import BeautifulSoup
import pandas as pd
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.remote_connection import LOGGER as seleniumLogger
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib3.connectionpool import log as urllibLogger

import common

# Avoid too much logging output from selenium and urllib.
seleniumLogger.setLevel(logging.WARNING)
urllibLogger.setLevel(logging.WARNING)

os.makedirs("work", exist_ok=True)
logging.basicConfig(
    filename="work/example.log",
    filemode="a",
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.DEBUG,
)


@common.with_session
def get_data_from_transfermarkt_de(session):
    # Parse all participants and their id.
    page = session.get(
        "https://www.transfermarkt.de/bundesliga/startseite/wettbewerb/L1"
    )
    page.raise_for_status()
    soup = BeautifulSoup(page.text, "html.parser")

    team_links = soup.find_all("a", href=True)
    teams = set()
    for link in team_links:
        href = link["href"]
        if "/startseite/verein/" in href and "saison_id/2023" in href:
            teams.add(href)
    assert len(teams) == 18, teams

    # Parse the player data team wise.
    def parse_market_value(market_value_str) -> int:
        market_value_list = market_value_str.split(" ", 2)
        if len(market_value_list) != 3:
            logging.warning(f"Invalid market value: {market_value_str}")
            return 0

        if not "€" in market_value_list[2]:
            logging.warning(
                f"Invalid currency: {market_value_list[2]}. Only euro supported."
            )
            return 0

        market_value = float(market_value_list[0].replace(",", "."))
        if "Tsd." in market_value_list[1]:
            market_value *= 10**3
        elif "Mio." in market_value_list[1]:
            market_value *= 10**6

        return int(market_value)

    # TODO: dict with duplicated player name or plain list?
    data = []
    for team_path in list(teams):
        team_url = "https://www.transfermarkt.de" + team_path
        logging.debug(f"{team_url=}")
        page = session.get(team_url)
        page.raise_for_status()
        soup = BeautifulSoup(page.text, "html.parser")

        players_row = soup.find_all(attrs={"class": "even"}) + soup.find_all(
            attrs={"class": "odd"}
        )

        for player in players_row:
            info = player.find_all(class_="hauptlink")[0]
            market_value = parse_market_value(player.find_all(class_="rechts")[0].text)
            # "nationality" means "team" in this case, in order to refactor less.
            data.append(
                {
                    "name_": info.text.strip(),
                    "market_value": market_value,
                    "nationality": team_path.split("/")[1],
                }
            )
    logging.debug("Transfermarkt data obtained.")
    return pd.DataFrame(data)


@common.with_driver
def get_available_players_fantasy(driver):
    def parse_ingame_value(ingame_value_str) -> int:
        ingame_value = float(ingame_value_str[:-1])
        value_prefix = ingame_value_str[-1]

        if value_prefix == "M":
            ingame_value *= 10**6
        else:
            raise ValueError(f"Invalid prefix: {value_prefix}")

        return int(ingame_value)

    driver.get("https://gaming.uefa.com/de/uefaeuro2020fantasyfootball/create-team")

    # wait until page is fully loaded
    player_filter = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "PlayreFilters"))
    )
    player_table = player_filter.find_element_by_css_selector("div[role='rowgroup']")

    # accept all cookies
    cookies_button = driver.find_element_by_id("onetrust-accept-btn-handler")
    cookies_button.click()

    def parse_playes_from_table(player_table):
        """Parse the players from the currently visible table section.
        The element stays the same, but the content changes.
        """
        player_data = set()
        players = player_table.find_elements_by_xpath("./div")
        for player in players:
            name_elem = player.find_element_by_class_name("si-plyr-name")
            value_elem = player.find_element_by_class_name("si-currency")
            currency_elem, value_elem = value_elem.find_elements_by_css_selector("span")
            position_elem = player.find_element_by_class_name("si-pos")
            if currency_elem.text != "€":
                logging.warning(f"Invalid currency {currency_elem.text}. Skipping.")
                continue
            if name_elem.text and position_elem.text and value_elem.text:
                player_data.add(
                    common.Player(
                        name=name_elem.text,
                        ingame_position=common.Position[position_elem.text],
                        ingame_value=parse_ingame_value(value_elem.text),
                    )
                )
            else:
                logging.warning(
                    f"Empty string: {name_elem.text}, {position_elem.text}, {value_elem.text}. Skipping."
                )
        return player_data

    player_data = set()
    wrapped_table = player_filter.find_element_by_class_name("si-list-wrap")
    slider_element = wrapped_table.find_element_by_xpath("div[1]/div/div[3]/div")
    last_slider_position = slider_element.location
    last_player_data = None
    while True:
        new_player_data = parse_playes_from_table(player_table)
        if last_player_data is not None and not (last_player_data & new_player_data):
            raise Exception("Scrolling failed. Common data is required.")
        last_player_data = new_player_data

        player_data.update(new_player_data)
        logging.debug(f"{len(player_data)} players parsed.")

        # Scroll down only a little bit to get the next players.
        # Couldn't find a better way for now.
        action = ActionChains(driver)
        action.click_and_hold(on_element=slider_element)
        action.move_by_offset(0, 7)
        action.perform()

        if last_slider_position == slider_element.location:
            break
        last_slider_position = slider_element.location

    return player_data


def match_first_letter(current_player, match_options):
    match_options_refined = []
    for option in match_options:
        if (
            current_player.first_name()[0] == option.first_name()[0]
            or current_player.first_name(special_chars=False)[0]
            == option.first_name(special_chars=False)[0]
        ):
            match_options_refined.append(option)
    if not match_options_refined:
        logging.debug("Couldn't find matching player. Skipping.")
        return None
    elif len(match_options_refined) == 1:
        logging.debug("Found matching player.")
        return match_options_refined[0]
    logging.debug("Found too many matching players. Skipping.")
    return None


def merge_player_data(available_players, player_data_transfermarkt):
    """Try to find stats for each available player by matching names."""
    # Special cases, because of different naming.
    special_mappings = {
        "A. Zabolotny": "Anton Zabolotnyi",
        "Danilo": "Danilo Pereira",
        "E. Bardi": "Enis Bardhi",
        "M. Kerem Aktürkoglu": "Kerem Aktürkoglu",
        "N. Nikolić": "Nemanja Nikolics",
        "T. Alcántara": "Thiago",
    }

    complete_players = []
    missing_players = []
    for player in available_players:
        logging.debug(f"Look up {player.name}.")

        possible_matches = []
        for p in player_data_transfermarkt:
            if p.family_name() == player.family_name():
                logging.debug("Found in normal lookup.")
                possible_matches.append(p)
            elif p.family_name(special_chars=False) == player.family_name(
                special_chars=False
            ):
                logging.debug("Found in lookup with special chars replaced.")
                possible_matches.append(p)
            elif special_mappings.get(player.name, "") == p.name:
                logging.debug("Found in lookup with hardcoded names.")
                possible_matches.append(p)

        matched_player = None
        if possible_matches:
            if len(possible_matches) == 1:
                logging.debug("Found matching player.")
                matched_player = possible_matches[0]
            else:
                logging.debug(
                    f"Too many family name matches: {possible_matches}. Try to find players via first letter of the first name {player.first_name()}."
                )
                matched_player = match_first_letter(player, possible_matches)
        else:
            logging.debug("Not found. Skipping.")

        if matched_player is not None:
            complete_players.append(matched_player + player)
        else:
            missing_players.append(player)

    logging.info(f"Complete_players: {len(complete_players)}")
    logging.info(
        f"Missing players: {len(missing_players)}: {[p.name for p in missing_players]}\n"
        + "The reason might be duplicated name, injury or dismissal."
    )
    return complete_players


def data_to_csv(data, file_):
    with open(file_, "w") as outfile:
        outfile.write(
            "\n".join(
                ["nationality,name_,cost_ingame,position,market_value"]
                + [
                    f"{p.nationality},{p.name},{p.ingame_value},{p.ingame_position.value},{p.market_value}"
                    for p in data
                ]
            )
        )


def get_data(filename, obtain_function, force):
    """Try to use cached data. If not possible, obtain data with function and write to cache."""
    if not os.path.isfile(filename) or force:
        data = obtain_function()
        with open(filename, "wb") as outfile:
            pickle.dump(data, outfile)
    else:
        logging.info(f'Use cached data from "{filename}".')
        with open(filename, "rb") as infile:
            data = pickle.load(infile)
    return data


def print_top_ratios(data):
    ratios = []
    for player in data:
        ratios.append(
            (
                player.market_value / player.ingame_value,
                player.market_value,
                player.ingame_value,
                player.ingame_position,
                player.name,
            )
        )
    for ratio in list(reversed(sorted(ratios)))[:20]:
        print(*ratio)


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
    args = parser.parse_args()

    player_data_transfermarkt = get_data(
        "work/transfermarkt.dat", get_data_from_transfermarkt_de, args.force
    )

    player_data_kicker = pd.read_csv(
        "https://classic.kicker-libero.de/api/sportsdata/v1/players-details/se-k00012023.csv",
        delimiter=";",
    )
    player_data_kicker = player_data_kicker.rename(
        columns={
            "Angezeigter Name": "name_",
            "Marktwert": "cost_ingame",
            "Position": "position",
        }
    )
    player_data_kicker["name_"] = player_data_kicker["name_"].str.lower()
    # special cases
    player_data_kicker["name_"] = player_data_kicker["name_"].apply(common.idfy)
    player_data_kicker["name_"] = (
        player_data_kicker["name_"]
        .str.replace("dion drena beljo", "dion beljo", regex=False)
        .str.replace("eric junior dina ebimbe", "junior dina ebimbe", regex=False)
        .str.replace("jean-manuel mbom", "jean manuel mbom", regex=False)
        .str.replace("kouadio kone", "manu kone", regex=False)
        .str.replace("omar haktab traore", "omar traore", regex=False)
        .str.replace("rafael santos borre", "rafael borre", regex=False)
    )
    player_data_transfermarkt["name_"] = player_data_transfermarkt["name_"].apply(
        common.idfy
    )
    player_data_transfermarkt["name_"] = player_data_transfermarkt["name_"].str.replace(
        "mateu morey bauzà", "mateu morey", regex=False
    )
    # use how="outer" for debugging
    player_data = player_data_kicker.merge(
        player_data_transfermarkt, on="name_", how="inner"
    )

    player_data.to_csv("work/test.csv")


if __name__ == "__main__":
    main()
