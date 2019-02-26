from read_wiki import search_wikipedia
import wikipedia
import gspread
from oauth2client.service_account import ServiceAccountCredentials

####
# 1. use a local 'apikey.json file to enable google spreadsheet API credentials'
# 2. SPREADSHEET_URL should be set after enabling token access to the relevant document
####

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1k18U6QQN94NwehUxK-p9sbUvCQZsuBHHhhnfiThWlj8/edit#gid=1064877315"

def read_google_spreadsheet():
    """
    get the existing db
    """
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    credentials = ServiceAccountCredentials.from_json_keyfile_name('apikeys.json', SCOPES)
    gc = gspread.authorize(credentials)
    spreadsheet = gc.open_by_url(SPREADSHEET_URL)
    worksheet = spreadsheet.get_worksheet(0)
    return worksheet


def update_worksheet(worksheet, lines_range=(2,20)):
    """
    Reads the lines in range, and query wikipedia + wikidata for the entity (fixed) name, update the rest of the fields in the row.
    Batch spreadsheet update (instead of a row-by-row.)
    """

    from read_wiki import fix_entry_name_options

    # define the range in the spreadsheet to update
    start_row = lines_range[0]
    end_row = lines_range[1]

    header = [cell.value for cell in worksheet.range("C1:G1")]   # get the header line keys

    all_cells = worksheet.range(f"C{start_row}:G{end_row}")
    summaries = []
    urls = []
    retrieved = {}

    row_length = 5    # assuming we are updating columns B:G
    number_of_rows = len(all_cells) / row_length

    cell_counter = 0

    for cell in all_cells:
        cell_type = header[cell_counter%row_length]

        if cell_type =='name':
            name = cell.value

            #if cell_counter % (row_length * 10) == 0:
            #        print(f"\nrow no. {int(cell_counter / row_length)}: {name}")

            if name in retrieved.keys():                   # check if we alrady retrieved this entitiy details
                entity_data = retrieved[name]
                # print(f"{name} detailes were alrady available locally")

            else:
                entity_data = search_wikipedia(name)
                # print(f"{name} detailes retrieved")

        else:
            if cell_type in entity_data:
                cell.value = str(entity_data[cell_type])          # update the cell value with the retrieved data
            else:
                cell.value = ""

        cell_counter +=1

        if (cell_counter % row_length == 0):
            try:
                print(name," ---> ",entity_data["wiki_title"])
            except:
                print(name," ---> ", "No wiki title found")
        if (cell_counter % (row_length*10) == 0):
            print(f"line {cell_counter/row_length}")
    worksheet.update_cells(all_cells)                        # batch saving on google spreadsheet

    return retrieved




def create_entities_list():
    """
    read all entities from the obudget API query endpointself.

    NOT READY YET!
    """
    import pandas as pd
    import requests

    biggest_id = 0

    status_code = 200                  # initialize requests status code

    while status_code == 200:
        query = f"https://next.obudget.org/api/query?query=select%20id,%20name,%20kind_he%20FROM%20entities_processed%20WHERE%20id%20%3E%20%27{biggest_id}%27%20ORDER%20BY%20id%20LIMIT%20100"  # order by the entity id, so we can iterate

        r = requests.get(query)
        status_code = r.status_code
        data = r.json()

        if biggest_id == 0:
            df = pd.DataFrame.from_dict(data["rows"])                   # creat the data frame on first iteration
        else:
            new_df = pd.DataFrame.from_dict(data["rows"])               # append data to the existing dataframe starting the 2nd iteration
            df.append(new_df)

        first_id = data["rows"][0]["id"]
        biggest_id = data["rows"][-1]["id"]                             # set the
        print(f"read items {first_id} - {biggest_id}" )
    return df
