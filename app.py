import requests
import hashlib
import hmac
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import toml
import altair as alt
import streamlit_authenticator as stauth

st.set_page_config(
    page_title='Employeee Survey Respondent',
    page_icon=':blue_heart:', 
)

# AUTHENTICATION SECTION

#Fetch credential
@st.cache_data(ttl=86400)  # Cache for 1 day
def fetch_data_creds():
    secret_info = st.secrets["sheets"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(secret_info, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open('Dashboard Credentials')
    sheet = spreadsheet.sheet1
    data = sheet.get_all_records()
    df_creds = pd.DataFrame(data)
    return df_creds

df_creds = fetch_data_creds()

def extract_credentials(df_creds):
    credentials = {
        "credentials": {
            "usernames": {}
        },
        "cookie": {
            "name": "growth_center",
            "key": "growth_2024",
            "expiry_days": 30
        }
    }
    for index, row in df_creds.iterrows():
        credentials['credentials']['usernames'][row['username']] = {
            'name': row['name'],  # Add the 'name' field
            'password': row['password'],  # Password should already be hashed
            'unit': row['unit'],  # Store the user's unit for later filtering
            'email': row['email'],      # Add the email field

        }
    return credentials

df_creds = fetch_data_creds()
credentials = extract_credentials(df_creds)

# Authentication Setup
authenticator = stauth.Authenticate(
    credentials['credentials'],
    credentials['cookie']['name'],
    credentials['cookie']['key'],
    credentials['cookie']['expiry_days']
)

# Display the login form
authenticator.login('main', fields = {'Form name': 'Welcome to Employee Survey Participation Dashboard'})
# Handle authentication status
if st.session_state['authentication_status']:
    username = st.session_state['username']

    # Retrieve the user's email and name from the credentials
    user_email = credentials['credentials']['usernames'][username]['email']
    user_name = credentials['credentials']['usernames'][username]['name']

        #ACCESS LOG
    def log_user_access(email):
        access_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Setup the Google Sheets client
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["sheets"], scope)
        client = gspread.authorize(creds)
        
        try:
            spreadsheet_id = "1Y6DN0bQd55Fbqygkb5hSNxJtC_l4U1QT2sBL-MR-K-4"  # Replace with your actual spreadsheet ID
            sheet = client.open_by_key(spreadsheet_id).sheet1  # Use open_by_key instead of open
            sheet.append_row([email, access_time])
        except gspread.SpreadsheetNotFound:
            st.write("Spreadsheet not found. Please check the ID and permissions.")
        except Exception as e:
            st.write(f"An error occurred: {e}")
    # Get the user's email from Streamlit's experimental_user function
    log_user_access(user_email)
    st.write(f"Welcome, {user_name} ({user_email})!")
    st.markdown("""
    <style>
    .header {
        background-color: #1DA1F2;  /* Twitter's blue */
        color: white;                /* White text */
        padding: 10px;               /* Padding for aesthetics */
        text-align: center;          /* Centered text */
        font-size: 24px;             /* Larger font size */
    }
    </style>
    <div class="header">
        <h1>🗨️Employee Survey Respondent</h1>
    </div>
    """, unsafe_allow_html=True)

    # FETCHING DATA FROM API SECTION 

    # Load secrets from secrets.toml
    secret_key = st.secrets["api"]["secret_key"]
    surresp_url = st.secrets["api"]["surresp_url"]  # Survey Respondent Data
    suransw_url = st.secrets["api"]["suransw_url"]  # Survey Answer Data

    # Function to generate HMAC-SHA256 using MD5 hash of date params
    def generate_code(start_date, end_date, secret_key):

        # Step 1: Create the MD5 hash from start and end dates
        date_string = f"{start_date.strftime('%Y-%m-%d %H:%M')}{end_date.strftime('%Y-%m-%d %H:%M')}"
        md5_hash = hashlib.md5(date_string.encode('utf-8')).hexdigest()

        # Step 2: Create HMAC-SHA256 using the MD5 hash and secret key
        secret = secret_key.encode('utf-8')
        code = hmac.new(secret, md5_hash.encode(), hashlib.sha256).hexdigest()

        return code

    # Function to fetch data from the API
    @st.cache_data(ttl=7200)
    def fetch_data(start_date, end_date, api_url):
        # Generate code for the date range
        code = generate_code(start_date, end_date, secret_key)
        
        # Format the start and end dates for the API request
        start_date_str = start_date.strftime("%Y-%m-%d %H:%M")
        end_date_str = end_date.strftime("%Y-%m-%d %H:%M")

        # Build the API URL
        url = api_url.format(start_date=start_date_str, end_date=end_date_str, code=code)

        # Fetch the data
        response = requests.get(url)

        # Check the response status
        if response.status_code == 200:
            print("Data fetched successfully!")
            return pd.DataFrame(response.json()["data"])  # Convert JSON to a DataFrame
        else:
            print(f"Failed to fetch data for {start_date_str} to {end_date_str}.")
            print(f"Status code: {response.status_code}")
            print(f"Response content: {response.content}")
            return None

    # Function to handle fetching Survey Respondent Data (24-hour intervals)
    @st.cache_data(ttl=7200)
    def fetch_survey_respondent_data(start_date, end_date):
        # --- Range survey: 1-30 Sept 2025 ---
        survey_start = datetime(2025, 9, 1, 0, 0)
        survey_end   = datetime(2025, 10, 10, 23, 59)
    
        # Handle kalau belum mulai
        if end_date < survey_start:
            st.warning("⏳ Survey belum dimulai (mulai 1 September 2025).")
            return pd.DataFrame(columns=["nik", "name", "unit_name", "div_name", "dept_name", "position_name", "submitted_on"])
    
        # Handle kalau sudah berakhir
        if start_date > survey_end:
            st.warning("✅ Survey sudah berakhir (sampai 30 September 2025).")
            return pd.DataFrame(columns=["nik", "name", "unit_name", "div_name", "dept_name", "position_name", "submitted_on"])
    
        all_data = []
        current_date = start_date
        total_days = max((end_date - start_date).days, 1)
    
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
    
        while current_date < end_date:
            next_date = (current_date + timedelta(days=1)).replace(hour=0, minute=0)
    
            # Update progress
            progress = min(((current_date - start_date).days + 1) / total_days, 1.0)
            progress_bar.progress(progress)
            status_text.write(
                f"Fetching data {current_date.strftime('%Y-%m-%d')} "
                f"s/d {next_date.strftime('%Y-%m-%d')}"
            )
    
            daily_data = fetch_data(current_date, next_date, surresp_url)
            if daily_data is not None and not daily_data.empty:
                all_data.append(daily_data)
    
            current_date = next_date
    
        # Bersihin progress
        progress_bar.empty()
        status_text.empty()
    
        # Kalau gak ada data sama sekali
        if not all_data:
            st.info("ℹ️ Tidak ada data responden di periode ini.")
            return pd.DataFrame(columns=["nik", "name", "unit_name", "div_name", "dept_name", "position_name", "submitted_on"])
    
        # Gabungkan semua
        combined_data = pd.concat(all_data, ignore_index=True)
    
        # Bersihin data testing
        if "name" in combined_data.columns:
            combined_data = combined_data[combined_data["name"] != "Testing aja"]
        else:
            st.warning("⚠️ Kolom 'name' tidak ada di survey respondent, skip filter Testing aja.")
    
        # Tambahkan kolom wajib kalau hilang
        required_cols = ["nik", "name", "unit_name", "div_name", "dept_name", "position_name", "submitted_on"]
        for col in required_cols:
            if col not in combined_data.columns:
                combined_data[col] = pd.NA
    
        return combined_data
    
    
    # --- Panggil fungsi ---
    start_date = datetime(2025, 9, 1, 0, 0)
    end_date   = datetime(2025, 10, 10, 23, 59)
    
    survey_respondent_data = fetch_survey_respondent_data(start_date, end_date)

    # CONNECT SHEET SAP SECTION

    # Fetch data
    @st.cache_data(ttl=86400)
    def fetch_data_sap():
        secret_info = st.secrets["sheets"]
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(secret_info, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open('0. Active Employee - Monthly Updated')
        sheet = spreadsheet.sheet1
        data = sheet.get_all_records()
        df_sap = pd.DataFrame(data)
        return df_sap

    # Finalize data
    df_sap = fetch_data_sap()

    # Display data from sap
    #with st.expander('Employee Data from SAP Sheet'):
        #st.dataframe(df_sap)
    #with st.expander('Survey'):
        #st.dataframe(survey_respondent_data)

    # --- JOIN SURVEY RESPONDENT AND SHEET SAP SECTION ---
    
    # Convert 'nik' column to string and ensure it is 6 digits starting with "00"
    survey_respondent_data['nik'] = survey_respondent_data['nik'].astype(str).str.zfill(6)
    df_sap['nik_short'] = df_sap['nik_short'].astype(str).str.zfill(6)

    # Now perform the merge
    df_merged = pd.merge(survey_respondent_data, df_sap, left_on='nik', right_on='nik_short', how='outer', indicator=True)

    # Convert submitted_on as datetime
    df_merged['submitted_on'] = pd.to_datetime(df_merged['submitted_on'], errors='coerce')

    # Display df_merged
    #with st.expander('Survey Respondent & SAP Sheet Merged'):
        #st.dataframe(df_merged)
    
    # Create the new concise DataFrame
    df_concise = pd.DataFrame({
        'nik': df_merged['nik_short'].combine_first(df_merged['nik_x']),
        'name' : df_merged['name_sap'].combine_first(df_merged['name']),
        'unit': df_merged['unit'].combine_first(df_merged['unit_name']),
        'subunit' : df_merged['subunit'].combine_first(df_merged['unit_name']),  # Fill empty subunit with unit
        'division': df_merged['division'].combine_first(df_merged['div_name']),
        'department': df_merged['department'].combine_first(df_merged['dept_name']),
        'position': df_merged['position'].combine_first(df_merged['position_name']),
        'phone_format': df_merged['phone_format'],
        'status_survey': df_merged['_merge'].apply(lambda x: 'done' if x in ['left_only', 'both'] else 'not done'),
        'admin_goman': df_merged.apply(lambda row: row['admin_goman'] if pd.notna(row['admin_goman']) else '-', axis=1),
        'submitted_on':df_merged['submitted_on'].dt.date
    })


    # Drop rows where the unit is 'KOMPAS GRAMEDIA'
    df_concise = df_concise.loc[df_concise['unit'] != 'KOMPAS GRAMEDIA'].reset_index(drop=True)
    df_concise = df_concise.loc[df_concise['unit'] != 'KG'].reset_index(drop=True)

    df_concise = df_concise.loc[df_concise['nik'] != '012172'].reset_index(drop=True)
    df_concise = df_concise.loc[df_concise['nik'] != '091412'].reset_index(drop=True)

    # Drop rows where the position is 'Store Apprentice'
    df_concise = df_concise.loc[df_concise['position'] != 'Store Apprentice'].reset_index(drop=True)
    df_concise.loc[df_concise['nik'] == '088367', 'unit'] = 'G. DYANDRA MEDIA INTERNATIONAL'
    df_concise.loc[df_concise['unit'] == 'REKATA', 'unit'] = 'G. RETAIL & PUBLISHING'

    import re

    def extract_main_unit(text):
        if pd.isna(text):
            return text

        # Convert non-string values to string
        text = str(text).strip()
        
        # Uppercase
        text = text.upper()
        
        # Ganti delimiter jadi satu (misalnya '/')
        text = re.sub(r'[-]', '/', text)
        
        # Replace phrases
        text = re.sub(r'GROUP\s+OF', 'G.', text, flags=re.IGNORECASE)
        text = re.sub(r'CORPORATE', 'C.', text, flags=re.IGNORECASE)
        text = re.sub(r'KOMPAS GRAMEDIA', '', text, flags=re.IGNORECASE)
        
        # Pecah berdasarkan '/'
        parts = [p.strip() for p in text.split('/') if p.strip()]
        
        # Cari yang dimulai "G." atau "C."
        for p in parts:
            if p.startswith("G.") or p.startswith("C."):
                return p.strip()
        
        # fallback: kalau ga ada "G." atau "C.", ambil bagian pertama setelah buang KG
        return parts[0] if parts else None


    # Terapkan ke dataframe
    df_concise['unit'] = df_concise['unit'].apply(extract_main_unit)
    # Normalisasi: strip spasi, uppercase, hapus titik dobel
    df_concise['unit'] = df_concise['unit'].str.upper().str.strip().str.replace(r'\s+', ' ', regex=True)
    
    # Mapping rename
    rename_units = {
        "G. DYANDRA MEDIA INTERNATIONAL": "DYANDRA",
        "DYANDRA MEDIA INTERNATIONAL": "DYANDRA",
        "G. HOTELS & RESORTS": "GOHR",
        "HOTELS & RESORTS": "GOHR",
        "G. RETAIL & PUBLISHING": "GORP",
        "RETAIL & PUBLISHING": "GORP",
        "G. MANUFACTURE" : "GOMAN",
        "G. MEDIA" : "KG MEDIA",
        "C. IT & IS" : "CITIS"
    }
    df_concise['unit'] = df_concise['unit'].replace(rename_units)
    df_concise['subunit'] = df_concise['subunit'].apply(extract_main_unit)


    # Convert the values to uppercase and remove spaces before and after
    df_concise['division'] = df_concise['division'].str.upper().str.strip()
    df_concise['department'] = df_concise['department'].str.upper().str.strip()

    #Display df_concise
    #with st.expander('df_concise'):
        #st.dataframe(df_concise)

    # FILTER SECTION

    # Sidebar: Add a selectbox for unit filter
    st.sidebar.markdown('### Unit Filter')

    # Multiselect widget to select multiple units
    unit_list = list(df_concise['unit'].unique())  # Remove 'All' for multiselect
    unit_list.insert(0, 'All')
    selected_unit = st.sidebar.multiselect('Select Unit:', unit_list, default=[])  # Pre-select all by default


    # Filter the DataFrame based on the selected units
    #if selected_unit:
        #df_concise = df_concise[df_concise['unit'].isin(selected_unit)]

    if selected_unit:
        if 'All' in selected_unit:
            df_concise = df_concise[df_concise['unit'] != 'G. DYANDRA MEDIA INTERNATIONAL']
        else:
            df_concise = df_concise[df_concise['unit'].isin(selected_unit)]

    # If 'G. MANUFACTURE' is in the selected units, show additional filter for 'Admin GOMAN'
    if 'GOMAN' in selected_unit:
        admin_goman_list = ['All'] + list(df_concise['admin_goman'].unique())
        selected_admin_goman = st.sidebar.multiselect('Select Admin GOMAN:', admin_goman_list)

        # Filter the DataFrame based on the selected 'Admin GOMAN'
        if selected_admin_goman:
            df_concise = df_concise[df_concise['admin_goman'].isin(selected_admin_goman)]

    # If 'G. MEDIA' is in the selected units, show additional filter for 'Admin GOMAN'
    if 'KG MEDIA' in selected_unit:
        subunit_list = ['All'] + list(df_concise['subunit'].unique())
        selected_subunit = st.sidebar.multiselect('Select Subunit KG MEDIA:', subunit_list)

        # Filter the DataFrame based on the selected 'Subunit GOMED'
        if selected_subunit:
            df_concise = df_concise[df_concise['subunit'].isin(selected_subunit)]

    division_list = list(df_concise['division'].unique())
    selected_division = st.sidebar.multiselect('Select Division:', division_list, default=[])

    if selected_division:
        df_concise = df_concise[df_concise['division'].isin(selected_division)]

    department_list = list(df_concise['department'].unique())
    selected_department = st.sidebar.multiselect('Select Department:', department_list, default=[])

    if selected_department:
        df_concise = df_concise[df_concise['department'].isin(selected_department)] 

    # Sidebar: Add a selectbox for breakdown variable
    st.sidebar.markdown ('### Breakdown Variable')
    breakdown_variable = st.sidebar.selectbox('Select Breakdown Variable:', ['unit', 'subunit', 'division', 'department'])

    # BAR CHART SECTION 

    # Create pivot table
    final_counts = df_concise.pivot_table(index=breakdown_variable, columns='status_survey', values='nik', aggfunc='nunique', fill_value=0).reset_index()

    # Ensure both 'Active Learners' and 'Passive Learners' columns exist
    if 'done' not in final_counts:
        final_counts['done'] = 0
    if 'not done' not in final_counts:
        final_counts['not done'] = 0

    # Ensure the correct order of columns before renaming
    final_counts = final_counts[[breakdown_variable, 'done', 'not done']]

    # Rename columns to 'Done' and 'Not Done'
    final_counts.columns = [breakdown_variable, 'Done', 'Not Done']

    # Calculate Done (%) and Not Done (%)
    final_counts['Done (%)'] = final_counts['Done'] / (final_counts['Done'] + final_counts['Not Done']) * 100
    final_counts['Not Done (%)'] = final_counts['Not Done'] / (final_counts['Done'] + final_counts['Not Done']) * 100

    # final_counts
    #with st.expander('Final Counts'):
        #st.write(final_counts)

    # Calculate overall status survey
    total_done = final_counts['Done'].sum()
    total_employee = final_counts['Done'].sum() + final_counts['Not Done'].sum()
    overall_status = (total_done / total_employee) * 100

    # Display the calculated percentage as a bar chart
    st.header(f'Overall Participation', divider='rainbow')

    # Display metrics column
    col1, col2, col3 = st.columns(3)
    col1.metric("Done", int(total_done))
    col2.metric("Total Employees", int(total_employee))
    col3.metric("Overall Participation", f"{overall_status:.2f}%")

    # Display the calculated percentage as a bar chart
    st.header(f'Survey Participation by {breakdown_variable.capitalize()}', divider='rainbow')

    # Transform data for Altair
    melted_counts = final_counts.melt(
        id_vars=breakdown_variable,
        value_vars=['Done', 'Not Done'],
        var_name='Survey Status',
        value_name='Count'
    )

    melted_percentage = final_counts.melt(
        id_vars=breakdown_variable,
        value_vars=['Done (%)', 'Not Done (%)'],
        var_name='Survey Status',
        value_name='Percent'
    )

    # Combine counts and percentage into a single DataFrame
    melted_counts['Percent'] = melted_percentage['Percent']

    # Create the chart
    participation_chart = alt.Chart(melted_counts).mark_bar().encode(
        y=alt.Y(f'{breakdown_variable}:N', sort='-x', axis=alt.Axis(title=breakdown_variable.capitalize())),
        x=alt.X('Percent:Q', axis=alt.Axis(title='Survey Participation (%)'), scale=alt.Scale(domain=[0, 100])),
        color=alt.Color('Survey Status:N', scale=alt.Scale(domain=['Done', 'Not Done'], range=['#1f77b4', '#ff7f0e'])),
        order=alt.Order('Survey Status:N', sort='ascending'),    # Ensure done is plotted first
        tooltip=[
            alt.Tooltip(f'{breakdown_variable}:N', title=breakdown_variable.capitalize()),
            alt.Tooltip('Survey Status:N', title='Survey Status'),
            alt.Tooltip('Count:Q', title='Count'),
            alt.Tooltip('Percent:Q', title='Percentage', format='.1f')
        ]
    ).properties(
        width=alt.Step(40)   # Adjust width as needed
    )

    # Display the chart using Streamlit
    #st.altair_chart(participation_chart, use_container_width=True)

    # Get the current date and calculate the target percentage based on the week
    current_date = datetime.now()
    start_percentage = 30  # Starting percentage on current date

    # Define the dates and the corresponding percentage increments
    increments = {
        datetime(2024, 10, 15): 70
    }

    # Dynamically determine the current percentage based on the date
    for target_date, percentage in increments.items():
        if current_date >= target_date:
            start_percentage = percentage

    # Create a dynamic vertical line (using `mark_rule`)
    vertical_line = alt.Chart(pd.DataFrame({'line': [start_percentage]})).mark_rule(color='red').encode(
        x='line:Q'
    )

    # Add a label next to the vertical line (using `mark_text`)
    vertical_line_label = alt.Chart(pd.DataFrame({'line': [start_percentage]})).mark_text(
        text='Target', align='left', dx=3, dy=-10, color='red', fontSize=12
    ).encode(
        x='line:Q',
        y=alt.value(10)  # Adjust the position on the Y-axis
    )

    # Combine the bar chart with the vertical line
    final_chart = participation_chart + vertical_line + vertical_line_label

    # Display the chart using Streamlit
    st.altair_chart(final_chart, use_container_width=True)

    # Add 'Achievement' column based on whether 'Done (%)' reaches the target
    final_counts['Target'] = final_counts['Done (%)'].apply(lambda x: 'Achieved' if x >= start_percentage else 'Not Achieved')

    # final_counts
    with st.expander('Data Source'):
        st.write(final_counts)

    # Display the resulting DataFrame
    df_concise2 = df_concise.drop(columns=['admin_goman'])
    with st.expander('Raw Data (Gunakan filter di sidebar dan klik tombol download di kanan atas tabel data)'):
        st.dataframe(df_concise2)

    # DAILY PROGRESS SECTION

    # Count rows for each date, keep None values
    count_by_date = df_concise.groupby('submitted_on').size().reset_index(name='count')

    # Remove rows with None dates for charting purposes
    count_by_date = count_by_date.dropna()

    # Create Altair chart
    progress_chart = alt.Chart(count_by_date).mark_line(point=True).encode(
        x=alt.X('submitted_on:T', title='Date', axis=alt.Axis(format='%d')),
        y=alt.Y('count:Q', title='Count'),
        tooltip=['submitted_on', 'count']
        )

    # Display the calculated percentage as a bar chart
    st.header(f'Daily Progress', divider='rainbow')

    # Display the chart using Streamlit
    st.altair_chart(progress_chart, use_container_width=True)

    # Display count_by_date
    with st.expander('Data Source 2'):
        st.dataframe(count_by_date) 
     # Logout button
    st.sidebar.markdown('### Options')
    authenticator.logout('Logout', 'sidebar')

elif st.session_state['authentication_status'] is False:
    st.error('Username/password is incorrect')
    
elif st.session_state['authentication_status'] is None:
    st.warning('Please enter your username and password')
