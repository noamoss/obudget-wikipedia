import requests
import wikipedia
from wikidata.client import Client
from urllib.parse import quote
import Levenshtein
import copy

acronyms = {                                         # here we gather all acronyms, to replace when querying wikipedia API
    'רוה"מ': 'ראש הממשלה',
    'צה"ל' : 'צבא ההגנה לישראל',
    'הלמ"ס': 'לשכה מרכזית לסטטיסטיקה',
    'משהב"ט': 'משרד הבטחון',
    'מע"מ' : 'מס ערך מוסף',
    'בי"ח' : 'בית חולים',
    'ביה"ח' : 'בית החולים',

    }


exception_entries = {                             # here we collect solutions for DisambiguationError response from the Wikiepdia's API calls
    'האקדמיה הלאומית למדעים': 'האקדמיה הלאומית הישראלית למדעים',
}


def get_synonyms(wikibase_item):
    """
    get the entity aliases
    """
    client = Client()  # doctest: +SKIP
    entity = client.get(wikibase_item, load=True) # get a wikidata.Entity object for Operation Protective Edge
    return entity.data['aliases'] # data is a dict inside the Entity object, 'aliases' returns all aliases for all the languages which have at least one alias for the label

def get_wikipedia_page_details(page_title):
    try:
        page = wikipedia.WikipediaPage(page_title)
        return {'wiki_summary': page.summary, 'wiki_url': page.url}
    except Exception as e:
        print(f"enounter an error communicatingn Wikipedia's API for {page_title}: {e}")
        return[""]


def words_list_to_title(words_list):
    """
    get words list, replace acrnyms and combine into a single string
    """
    fixed_title_words = []
    for word in words_list:
        if word in acronyms:
            fixed_title_words.append(acronyms[word])
        else:
            fixed_title_words.append(word)
    return " ".join(fixed_title_words)


def fix_entry_name_options(entry_name):
    """
    fix the entry name to fit query
    """

    options = []
    results = []

    options.append(entry_name.replace("/"," ").split(" "))
    if "/" in entry_name:
        options.append(entry_name.split("/")[0].split(" "))
        options.append(entry_name.split("/")[1].split(" "))

    if "-" in entry_name:
        options.append(entry_name.split("-")[0].split(" "))
        options.append(entry_name.split("-")[1].split(" "))

    for option in options:
        new_option = words_list_to_title(option)

        if new_option in exception_entries.keys():                # verify we did not encounter past DisambiguationError for the value before
            results.append(exception_entries[new_option])
        else:
            results.append(words_list_to_title(option))
    return results


def search_wikipedia(entry_name):
    optional_entries = fix_entry_name_options(entry_name)
    # retrieve the first result title from wikipedia
    wikipedia.set_lang('he')

    def wiki_search_term(term):
        """
        Check on the wikipedia API for term relevant page titles
        """
        result = wikipedia.search(term)
        if len(result) == 0:
            return [""]
        else:
            return result


    try:                                                                    # pack and all relevant page titles (options) and their ratio score, to decide which one should be chosen
        wikipedia_query_results = [x[0] for x in list(map(wiki_search_term, optional_entries))]
        wiki_options_ratios = list(map(Levenshtein.ratio, wikipedia_query_results,optional_entries))
        options = list(zip(wikipedia_query_results, wiki_options_ratios))
        options = sorted(options, key=lambda x: x[1], reverse=True)

        #print(f"options and ratios for {entry_name}: \n{options}\n")
        first_option_query, first_option_score = options[0][0], options[0][1]           # logic for choosing the right entry+page
        fixed_entry_name = first_option_query
        best_score = first_option_score

        if len(options) > 1 and "משרד" in first_option_query:
            second_option_query, second_option_score = options[1][0], options[1][1]
            if second_option_score > 0.7:
                fixed_entry_name = second_option_query
                best_score = second_option_score


        if best_score < 0.5:
            print(f"low ration of similiarity for {entry_name}, no data to be saved on table")
            return {}


    except Exception as e:
        print(f"wikipedia_query_result issue for {entry_name}: {e}")
        return {}

    # get the wikipedia id and page title for the chosen page
    wikipedia_api_url = f"https://he.wikipedia.org/w/api.php?action=query&prop=pageprops&ppprop=wikibase_item&redirects=1&format=json&titles={fixed_entry_name}"
    page_details = list(requests.get(wikipedia_api_url).json()['query']['pages'].values())[0]

    wiki_title = page_details['title']
    try:
        wikibase_item = page_details['pageprops']['wikibase_item']
    except Exception as e:
        print(f"Could not find wikibase item entry for {fixed_entry_name}: {e}")
        wikibase_item = ""

    # look for snynyms using Wikidata
    wiki_synonyms = dict(get_synonyms(wikibase_item))
    if 'he' in wiki_synonyms.keys():
        wiki_synonyms = [result['value'] for result in wiki_synonyms['he']]
    else:
        wiki_synonyms = []

    # get the page summary
    results = get_wikipedia_page_details(wiki_title)

    results['wiki_title'] = wiki_title
    results['wiki_synonyms'] = wiki_synonyms

    return results
