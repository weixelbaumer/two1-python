import datetime
from textwrap import wrap

import click
from tabulate import tabulate
from two1.commands import formatters
from two1.commands.config import TWO1_HOST
from two1.lib.server.analytics import capture_usage
from two1.lib.server.rest_client import ServerRequestError
from two1.lib.util.decorators import json_output
from two1.lib.util.uxstring import UxString
from two1.lib.server import rest_client


@click.command("search")
@click.pass_context
@click.argument('search_string', required=False)
@json_output
def search(config, search_string=None):
    """Search for app on the 21 Marketplace.

\b
Usage
-----
View all the apps in the marketplace
$ 21 search

\b
Search for specific keywords or terms
$ 21 search "games social"

\b
Search for all the apps from a particular user
$ 21 search "snakamoto"

Results from the search command are paginated.
Use 'n' to move to the next page and 'p' to move to the previous page.

You can view detailed information about an app by specifying it's id
at the prompt.

    """
    _search(config, search_string)


@capture_usage
def _search(config, search_string):
    client = rest_client.TwentyOneRestClient(TWO1_HOST,
                                             config.machine_auth,
                                             config.username)
    if search_string is None:
        click.secho(UxString.list_all, fg="green")

    current_page = 0
    row_id_to_model_id = {}
    total_pages = get_search_results(client, search_string, current_page,
                                     row_id_to_model_id)
    if total_pages < 1:
        return

    while 0 <= current_page < total_pages:
        try:
            prompt_resp = click.prompt(UxString.pagination,
                                       type=str)
            try:
                index = int(prompt_resp)
                if index not in row_id_to_model_id:
                    raise ValueError

                model_id = row_id_to_model_id[index]
                display_search_info(config, client, model_id)

            except ValueError:

                next_page = get_next_page(prompt_resp, current_page)

                if next_page >= total_pages or next_page < 0:
                    continue
                else:
                    get_search_results(client, search_string, next_page,
                                       row_id_to_model_id)
                    current_page = next_page

        except click.exceptions.Abort:
            return


def get_search_results(rest_client, search_string, page, row_id_to_model_id):
    resp = rest_client.search(search_string, page)
    if resp.ok:
        resp_json = resp.json()
        search_results = resp_json["results"]
        if search_results is None or len(search_results) == 0:
            click.secho(UxString.empty_listing.format(search_string))
            return 0

        total_pages = resp_json["total_pages"]
        click.secho("\nPage {}/{}".format(page + 1, total_pages), fg="green")
        content = market_search_formatter(search_results, page, row_id_to_model_id)
        click.echo(content)
        return total_pages
    else:
        raise ServerRequestError()


MAX_PAGE_SIZE = 10


def market_search_formatter(search_results, current_page, row_id_to_model_id):
    headers = ["id", "Details", "Creator", "price range", "category"]
    rows = []
    for i, item in enumerate(search_results):
        id = click.style(str((current_page * MAX_PAGE_SIZE) + i + 1), fg="blue")
        price_range = click.style("{} - {} Satoshis".format(item["min_price"],
                                                            item["max_price"]), fg="blue")

        category = click.style("{}".format(item["category"]), fg="blue")
        creator = click.style("{}".format(item["username"]), fg="blue")
        title = click.style(item["title"], fg="blue")
        rows.append([id, title, creator, price_range, category])
        rows.append(["", "", "", "", ""])
        for indx, l in enumerate(wrap(item["description"])):
            rows.append(["", l, "", "", ""])
        rows.append(["", "", "", "", ""])

    return tabulate(rows, headers=headers, tablefmt="psql")
def get_next_page(prompt_response, current_page):
    if prompt_response.lower() in ["n", "next", "f", "forward"]:
        return current_page + 1
    elif prompt_response.lower() in ["p", "previous", 'b', "back"]:
        return current_page - 1
    elif prompt_response.lower() in ["q", "cancel", "c"]:
        raise click.exceptions.Abort()
    else:
        return -1


def display_search_info(config, client, listing_id):
    resp = client.get_listing_info(listing_id)
    if resp.ok:
        result_json = resp.json()
        title = click.style("App Name     : ", fg="blue") + click.style(
            "{}".format(result_json["title"]))
        created_by = click.style("Created By   : ", fg="blue") + click.style(
            "{}".format(result_json["username"]))

        desc = click.style("Description  : ", fg="blue") + click.style(
            "{}".format(result_json["description"]))
        price = click.style("Price Range  : ", fg="blue") + click.style(
                "{} - {} Satoshis").format(result_json["min_price"],
                                           result_json["max_price"])

        doc_url = click.style("Docs URL     : ", fg="blue") + click.style(
            "{}".format(result_json["website_url"]))
        app_url = click.style("App URL      : ", fg="blue") + click.style(
            "{}".format(result_json["app_url"]))
        category = click.style("Category     : ", fg="blue") + click.style(
            "{}".format(result_json["category"]))
        keywords = click.style("Keywords     : ", fg="blue") + click.style(
            "{}".format(', '.join(result_json["keywords"])))
        version = click.style("Version      : ", fg="blue") + click.style(
            "{}".format(result_json["version"]))
        last_updated_str = datetime.datetime.fromtimestamp(
            result_json["updated"]).strftime("%Y-%m-%d %H:%M")
        last_update = click.style("Last Update  : ", fg="blue") + click.style(
            "{}".format(last_updated_str))
        quick_start = click.style("Quick Start\n\n", fg="blue") + click.style(
            result_json["quick_buy"]
        )
        is_active = click.style("Status       : ", fg="blue")
        if result_json["is_active"] and result_json["is_up"] and result_json[
            "is_healthy"]:
            is_active += click.style("Active")
        else:
            is_active += click.style("Inactive")

        availability = click.style("Availability : ", fg="blue") + click.style(
                "{:.2f}%".format(result_json["average_uptime"] * 100))

        usage_docs = click.style("Detailed usage\n\n", fg="blue") + click.style(
            result_json["usage_docs"])

        final_str = "\n".join(
                [title, desc, created_by, price,"\n",
                 is_active, availability, "\n",
                 doc_url, app_url, "\n",
                 category, keywords, version, last_update, "\n",
                 quick_start, "\n",
                 usage_docs, "\n\n"])
        config.echo_via_pager(final_str)
    else:
        raise ServerRequestError()
