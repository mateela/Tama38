from bs4 import BeautifulSoup
from selenium import webdriver
import pandas as pd
from datetime import datetime

CHROME_DRIVER_PATH = "C:\ChromeDriver\chromedriver.exe"
NEW = "new"
AVAILABLE = "available"
LOW = "low"
HIGH = "high"
TAMA_38 = "tama_38"
DOC_TYPE_INDEX = 1
DOC_DATE_INDEX = 0
NOT_SPECIFIED = "not specified"


def main():

    # create savings tracking file:
    now = datetime.now()
    program_start_time = now.strftime("%Y_%m_%d__%H_%M")
    with open("savings_tracker" + program_start_time + ".txt", 'a+') as file:
        file.write("The program started running at: " + program_start_time + "\n")

    # initiate Data Frame for houses data:
    data = pd.DataFrame(columns=['Tikid', 'Street_name', 'House_num', 'Bloc', 'Site', 'Label'])

    # read streets data to parse on:
    streets_data = pd.read_csv("qr4_tama38_Left_side.csv")

    # open web driver:
    driver = webdriver.Chrome(CHROME_DRIVER_PATH)

    # run on relevant urls:
    for index, row in streets_data.iterrows():
        street_num = str(row['street_num'])
        lower_bound = row['lower_bound']
        upper_bound = row['upper_bound']

        url = "https://archive-binyan.tel-aviv.gov.il/pages/results.aspx?owsTikid={}"

        for i in range(lower_bound, upper_bound + 1):

            house_city_code = get_house_city_code(street_num, str(i))

            try:
                data = parse_single_house(driver, url.format(house_city_code), data)
            except (IndexError, MemoryError, RuntimeError):
                continue

            # # for houses with entrance 'A':
            # house_city_code = house_city_code[:-1] + "1"
            # data = parse_single_house(driver, url.format(house_city_code), data)

        # save results at the end of each street:
        temp_save(data, program_start_time)

    # close driver
    driver.quit()

    # save final result in the results file:
    data.to_csv(r"C:\Users\Administrator\Documents\tama38_project\tama_38_project.csv", index=False,
                encoding='utf-8-sig')


def temp_save(data, program_start_time):

    temp_save.__dict__.setdefault('count', 1)

    # save results in the results file:
    data.to_csv(r"C:\Users\Administrator\Documents\tama38_project\tama_38_project.csv", index=False,
                encoding='utf-8-sig')

    # keep track of each save in a single file:
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    with open("savings_tracker" + program_start_time + ".txt", 'a+') as file:
        file.write("The time of save number " + str(temp_save.count) + " is: " + current_time + "\n")

    temp_save.count += 1


def get_house_city_code(street_num, house_num):
    while len(street_num) < 4:
        street_num = "0" + street_num

    while len(house_num) < 3:
        house_num = "0" + house_num

    return street_num + house_num + "0"


def get_house_address_and_blocks(soup):
    address = soup.find("div", {"class": "addresses"}).ul.li.text
    street_name = ""
    house_num = ""
    for i in range(len(address)):
        if address[i].isdigit():
            street_name = address[:i]
            house_num = address[i:]
            break

    bloc = NOT_SPECIFIED  # in hebrew - GUSH
    site = NOT_SPECIFIED  # in hebrew - CHELKA

    blocks = soup.find("div", {"class": "blocks"})
    info = blocks.ul.li.text.split("/")

    if len(info) > 1:
        bloc = info[0]
        site = info[1]

    return street_name, house_num, bloc, site


def parse_single_house(driver, url, data):
    driver.get(url)
    check = driver.find_elements_by_class_name("arc-button-big")

    # check that the url leads to a correct page:
    if len(check) > 0:
        check[0].click()
    elif len(driver.find_elements_by_class_name("addresses")) == 0:
        return data

    # parse the html in the file:
    page_full_html = driver.execute_script("return document.documentElement.outerHTML")
    soup = BeautifulSoup(page_full_html, "html.parser")

    # extract building address and blocks number:
    street_name, house_num, bloc, site = get_house_address_and_blocks(soup)

    # extract all relevant information for classification of the address:
    all_docs = []
    extract_info(all_docs, driver, soup)

    # classify building:
    label = classify_building(all_docs)

    data = data.append({'Tikid': url[-8:], 'Street_name': street_name, 'House_num': house_num, 'Bloc': bloc,
                        'Site': site, 'Label': label}, ignore_index=True)
    return data


def extract_info(all_docs, driver, soup):

    # extract most recent document data to all_docs[0]:
    doc_dates = soup.findAll("span", {"class": "doc-date"})
    doc_types = soup.findAll("span", {"class": "document-type"})

    # we assume here that the most recent document on the table as a legal date in shape of DD/MM/YYYY.
    all_docs.append((doc_dates[0].text, doc_types[0].text))

    # fill the rest of the documents, including only those from the last 15 years:
    for i in range(1, len(doc_dates)):
        # ensuring legal input:
        doc_date = doc_dates[i].text
        if doc_date != "" and get_year(doc_date) >= 2005:
            all_docs.append((doc_dates[i].text, doc_types[i].text))
        else:
            break

    next_page = driver.find_elements_by_class_name("next")

    while len(next_page) > 0:
        next_page[0].click()
        page_full_html = driver.execute_script("return document.documentElement.outerHTML")
        soup = BeautifulSoup(page_full_html, "html.parser")

        doc_dates = soup.findAll("span", {"class": "doc-date"})
        doc_types = soup.findAll("span", {"class": "document-type"})

        for i in range(len(doc_dates)):
            # ensuring legal input:
            doc_date = doc_dates[i].text
            if doc_date != "":
                if get_year(doc_date) >= 2005:
                    all_docs.append((doc_dates[i].text, doc_types[i].text))
                else:
                    break
        else:
            next_page = driver.find_elements_by_class_name("next")
            continue
        break

    # extract the oldest document data to all_docs[-1]:
    last_page = driver.find_elements_by_class_name("last")
    if len(last_page) > 0:
        last_page[0].click()
        page_full_html = driver.execute_script("return document.documentElement.outerHTML")
        soup = BeautifulSoup(page_full_html, "html.parser")

        doc_dates = soup.findAll("span", {"class": "doc-date"})
        doc_types = soup.findAll("span", {"class": "document-type"})

    for i in reversed(range(len(doc_dates))):
        # ensuring legal input:
        if doc_dates[i].text != "":
            all_docs.append((doc_dates[i].text, doc_types[i].text))
            return

    previous_page = driver.find_elements_by_class_name("prev")

    while len(previous_page) > 0:
        previous_page[0].click()
        page_full_html = driver.execute_script("return document.documentElement.outerHTML")
        soup = BeautifulSoup(page_full_html, "html.parser")

        doc_dates = soup.findAll("span", {"class": "doc-date"})
        doc_types = soup.findAll("span", {"class": "document-type"})

        for i in reversed(range(len(doc_dates))):
            # ensuring legal input:
            if doc_dates[i].text != "":
                all_docs.append((doc_dates[i].text, doc_types[i].text))
                return

        previous_page = driver.find_elements_by_class_name("prev")


def classify_building(all_docs):
    # checking if this is a new building:
    oldest_doc_date = get_year(all_docs[-1][DOC_DATE_INDEX])
    if oldest_doc_date > 1980:
        return NEW

    # checking if this is an available building:
    newest_doc_date = get_year(all_docs[0][DOC_DATE_INDEX])
    if newest_doc_date <= 1980:
        return AVAILABLE

    # limiting documents only from the last 15 years
    last_15_years_docs = [doc for doc in all_docs if get_year(doc[DOC_DATE_INDEX]) >= 2005]

    # checking for indicative documents:
    form_no_4, form_no_1, simulations, area_comp = False, False, False, False
    for doc in last_15_years_docs:
        if doc[DOC_TYPE_INDEX] == "טופס 4":
            form_no_4 = True

        if doc[DOC_TYPE_INDEX] == "טופס 1":
            form_no_1 = True

        if doc[DOC_TYPE_INDEX] == "הדמיות":
            simulations = True

        if doc[DOC_TYPE_INDEX] == "חישוב שטחים":
            area_comp = True

    # presence of this document in the last 15 years is a certain indication that the building had tama 38
    if form_no_4:
        return TAMA_38

    # presence of this documents in the last 15 years is a strong indication that the building had tama 38
    if form_no_1 or simulations or area_comp:
        return HIGH

    # this amount of documents in the last 15 years is a wick indication that the building had tama 38
    if len(last_15_years_docs) >= 10:
        return LOW

    # in the lack of presence for any indicators we mark the building as available:
    return AVAILABLE


def get_year(date):
    return int(date.split("/")[2])


if __name__ == '__main__':
    main()
