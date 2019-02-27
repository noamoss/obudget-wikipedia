from read_wiki import search_wikipedia, update_obudget_wikipedia_categories_table
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
    update_obudget_wikipedia_categories_table      # update the relevant wikipedia categories lists per obudget 'he_kind'

    # define the range in the spreadsheet to update
    start_row = lines_range[0]
    end_row = lines_range[1]
    print(f"start row: {start_row}   end row: {end_row}")

    header = worksheet.row_values(1)   # get the header line keys

    all_cells = []
    summaries = []
    urls = []
    retrieved = {}

    number_of_rows = end_row - start_row

    for row_index in range(start_row, end_row):
        row_values = worksheet.row_values(row_index)
        entity_data = {}

        for cell_index in range(len(header)):
            try:
                cell_value = row_values[cell_index]
            except:
                cell_value = ''
            cell_type = header[cell_index]
            #print(f"row index {row_index} cell index {cell_index}, cell type {cell_type}")

            if cell_type =='id':
                pass
            elif cell_type =='kind_he':
                if cell_value == '' or cell_value == None:
                    obudget_category = None
                else:
                    obudget_category = cell_value

            elif cell_type =='name':
                name = cell_value
                if  name != '' and name != None:
                    if name in retrieved.keys():                   # check if we alrady retrieved this entitiy details
                        entity_data = retrieved[name]
                        # print(f"{name} detailes were alrady available locally")

                    else:
                        #print(f"searching {name}, with obudget category {obudget_category}")
                        entity_data = search_wikipedia(name, obudget_category)
                        # print(f"{name} detailes retrieved")
                else:
                    entity_data = {}

            else:
                if cell_type in entity_data:
                    cell_value = str(entity_data[cell_type])          # update the cell value with the retrieved data
                    #print(f"{name} {cell_type}: {cell_value}")
                else:
                    #print(f"no {cell_type} value for {name}")
                    cell_value = ''

            try:
                all_cells.append(gspread.Cell(row_index, cell_index+1, cell_value))
            except Exception as e:
                print(f"Error while updating row no. {row_index} column {cell_index} for {name}: {e}")

        if "wiki_title" in entity_data:
            print(f"{row_index}. {name} --> {entity_data['wiki_title']}")
        else:
            print(f"{row_index}. {name} ---> no wiki entry")

    try:
        worksheet.update_cells(all_cells)                        # batch saving on google spreadsheet
        print(f"updated google spreadsheet")

    except Exception as e:
        print(f" Error trying to update google spreadsheet")

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
