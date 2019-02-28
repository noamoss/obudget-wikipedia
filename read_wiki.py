import requests
import wikipedia
from wikidata.client import Client
from urllib.parse import quote
import Levenshtein
import copy

wikipedia_api_url = "https://he.wikipedia.org/w/api.php"

obudget_wikipedia_categories_table = {
    'משרד ממשלתי':
        ['נשיא מדינת ישראל',
         'הכנסת',
         'הוועדה לאנרגיה אטומית',
        ],

}

def update_obudget_wikipedia_categories_table():
    """
    Get from the wikipedia API subcategories of all given obudget categories ('he_kind')
    """

    PARAMS = {
        'action': "query",
        'list': "categorymembers",
        'cmtitle': '',                    # this will be changed as we iterate
        'cmtype':'subcat',
        'format': "json"
    }

    api_update_urls = {
        'משרד ממשלתי':
            [   'קטגוריה:משרד ראש הממשלה',
                'קטגוריה:משרדי ממשלה בישראל',
                'קטגוריה:ארגונים ממשלתיים',
                'קטגוריה:צה"ל: זרועות ופיקודים',
                'קטגוריה:בתי חולים פסיכיאטריים ממשלתיים',
                'קטגוריה:משטרת ישראל',
                'קטגוריה:המשרד לבטחון פנים',
                'קטגוריה:משרד המשפטים',
                'קטגוריה:ישראל: חוק ומשפט',
                'קטגוריה:משרד הביטחון'
            ]

        }

    for key, wiki_categories in api_update_urls.items():
        subcategoires = []
        items_to_add = []
        for category in wiki_categories:
            PARAMS["cmtitle"] = category
            r = requests.get(wikipedia_api_url, PARAMS).json()
            subcategories = [item['title'] for item in r['query']['categorymembers']]
            items_to_add += [category.replace('קטגוריה:','')] + [item['title'].replace('קטגוריה:','') for item in r['query']['categorymembers']]
            for subcategory in subcategories:
                try:
                    PARAMS["cmtitle"] = subcategory
                    r = requests.get(wikipedia_api_url, PARAMS).json()
                    items_to_add += [item['title'].replace('קטגוריה:','') for item in r['query']['categorymembers']]

                except:
                    print(f" failed loading subcategories for {subcategory}")
        obudget_wikipedia_categories_table[key] += items_to_add

    return obudget_wikipedia_categories_table

acronyms = {                                         # here we gather all acronyms, to replace when querying wikipedia API
    'רוה"מ': 'ראש הממשלה',
    'צה"ל' : 'צבא ההגנה לישראל',
    'הלמ"ס': 'הלשכה המרכזית לסטטיסטיקה',
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


def words_list_to_title(words_list):
    """
    get words list, replace acronyms and combine into a single string
    """
    fixed_title_words = []
    for word in words_list:
        if word in acronyms:
            fixed_title_words.append(acronyms[word])
        else:
            fixed_title_words.append(word)
    return " ".join(fixed_title_words).strip()


def fix_entry_name_options(entry_name):
    """
    generate list of relevant queries based on a given entry_name
    """
    wikipedia.set_lang('he')
    options = []
    results = []

    options.append(entry_name.replace("/"," ").split(" "))
    options.append([word for word in entry_name.replace("המשרד",'').replace("משרד","").replace("/"," ").split(" ") if word !=''])

    if "/" in entry_name:
        splitted = entry_name.split("/")
        for new_option in splitted:
            if new_option!='':
                options.append(new_option.split(" "))
    if "-" in entry_name:
        splitted = entry_name.split("/")
        for new_option in splitted:
            if new_option!='':
                options.append(new_option.split(" "))

    for option in options:
        new_option = words_list_to_title(option)
        if '"' not in new_option:
            try:
                wikipedia_search_suggestions = wikipedia.search(new_option)
                for suggestion in wikipedia_search_suggestions:
                    if Levenshtein.ratio(suggestion, new_option) > 0.7:
                        #print(f"added '{suggestion}' from wikipedia suggested entries for {option}")
                        results.append(wikipedia.search(new_option)[0])
            except Exception as e:
                print(f"wiki alternatives search error for {new_option} (part of '{entry_name}' query): {e}")
                pass

        if new_option in exception_entries.keys():                # verify we did not encounter past DisambiguationError for the value before
            results.append(exception_entries[new_option])
        else:
            results.append(words_list_to_title(option))
            if '"' in new_option:                                   # try also without apostrophes
                results.append(words_list_to_title([new_option]))
    return list(set(results))


def extract_page_categories(page_data):
    try:
        if "categories" in page_data:
            return [category["title"].replace('קטגוריה:','') for category in page_data["categories"]]
        else:
            return []
    except Exception as e:
        print(f"Could not extract categories for {page_data}\n \n {e}")


def filter_page_by_category(obudget_category):
    def check_relevant_entries_by_category(page_data):
        try:
            current_page_categories = set(page_data["categories"])
            relevant_wiki_categories = set(obudget_wikipedia_categories_table[obudget_category])                     # translate the obudget category to the wikipedia categories list
            return len(current_page_categories.intersection(relevant_wiki_categories)) > 0
        except:
            return False
    return check_relevant_entries_by_category

def wiki_search_terms(terms):
    """
    Get from the wikipedia API for term relevant page titles and details
    """

    if type(terms) == str:             # set the correct query string
        titles=terms
    elif type(terms)==list:
        if len(terms)==1:
            titles = terms[0]
        else:
            titles = "|".join(terms)

    payload = {
        "action": "query",
        "prop":"extracts|pageprops|categories|info",
        "cllimit": 200,
        "inprop":"url",
        "exintro":True,
        "explaintext":True,
        "redirects": True,
        "format": "json",
        "titles": titles,
    }

    query_results = requests.get(wikipedia_api_url, payload).json()["query"]
    query_results["pages"] = [result for result in list(query_results["pages"].values()) if 'missing' not in result]

    for page_data in query_results["pages"]:
        page_data["categories"] = extract_page_categories(page_data)
    return query_results



def search_wikipedia(entry_name, obudget_category=None):
    optional_entries = fix_entry_name_options(entry_name)

    try:                                                                    # pack and all relevant page titles (options) and their ratio score, to decide which one should be chosen
        wikipedia_query_results = wiki_search_terms(optional_entries)

        if "pages" in wikipedia_query_results and obudget_category != None:
            makefilter = filter_page_by_category(obudget_category)
            wikipedia_query_results["pages"] = list(filter(makefilter, wikipedia_query_results["pages"]))
            if len(wikipedia_query_results["pages"]) == 0:
                print(f"left with no results for {entry_name} after filtering for {obudget_category} obudget category. Better check it out")
        if len(wikipedia_query_results["pages"]) > 1:
            titles_to_compare = []

            for page_index, page in enumerate(wikipedia_query_results["pages"]):
                if "redirects" in wikipedia_query_results["pages"][page_index].keys():
                    title_to_compare = wikipedia_query_results["pages"][page_index]["redirects"][0]["from"]

                else:
                    title_to_compare = wikipedia_query_results["pages"][page_index]["title"]

                wikipedia_query_results["pages"][page_index]["title_to_compare"] = title_to_compare
                titles_to_compare.append(title_to_compare)

            wiki_options_ratios = list(map(Levenshtein.ratio, optional_entries, titles_to_compare))
            options = list(zip(wikipedia_query_results["pages"], wiki_options_ratios))
            options = sorted(options, key=lambda x: x[1], reverse=True)

            first_option_query, first_option_score = (options[0][0], options[0][1])           # logic for choosing the right entry+page
            fixed_entry_name = first_option_query["title_to_compare"]
            best_score = first_option_score
            results = first_option_query

            second_option_query, second_option_score = (options[1][0], options[1][1])

            if len(options) > 1 and "משרד" in first_option_query["title_to_compare"]:
                if second_option_score > 0.7:
                    fixed_entry_name = second_option_query["title_to_compare"]
                    best_score = second_option_score
                    results = second_option_query


            if best_score < 0.5:
                print(f"low ration of similiarity for {entry_name}, no data to be saved on table")
                return {}

        else:
            results = wikipedia_query_results["pages"][0]

    except Exception as e:
        print(f"wikipedia_query_result issue for {entry_name}: {e}")
        return {}

    # look for snynyms using Wikidata
    if "pageprops" in results.keys() and "wikibase_item" in results["pageprops"].keys():
            wikibase_item = results["pageprops"]["wikibase_item"]
            wiki_synonyms = dict(get_synonyms(wikibase_item))
            if 'he' in wiki_synonyms.keys():
                wiki_synonyms = [result['value'] for result in wiki_synonyms['he']]
            else:
                wiki_synonyms = []

            results['wiki_synonyms'] = wiki_synonyms
    else:
        print(f"can't find wikibase for synyms for {entry_name}: {results}")

    try:
        return {"wiki_title":results["title"], "wiki_summary":results["extract"], "wiki_synonyms":results["wiki_synonyms"], "wiki_url":results["fullurl"], "wiki_categories":results["categories"]}
    except Exception as e:
        print(f"error with the result record of {entry_name}: \n {results} \n {e}")
