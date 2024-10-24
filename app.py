from flask import Flask, request, redirect, render_template, send_file
import pandas as pd
import os

app = Flask(__name__)

# Folder to store uploaded and processed files
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(PROCESSED_FOLDER):
    os.makedirs(PROCESSED_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# Route for the homepage
@app.route('/')
def home():
    return render_template('upload.html')


# Route to handle the CSV file upload and processing
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect('/')

    file = request.files['file']

    if file.filename == '':
        return redirect('/')

    if file:
        # Save the uploaded file
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        # Process the file and generate the output
        processed_filepath = process_file(filepath)

        # Return the download link for the processed file
        return send_file(processed_filepath, as_attachment=True)


def process_file(filepath):
    # Reading the CSV file
    orders = pd.read_csv(filepath)

    # Renaming columns for easier access
    orders.columns = ['Order ID', 'Order Date', 'Invoice', 'Checkout Price', 'VAT Amount', 'Supplier',
                      'VAT == 1/6 Checkout Price']

    # Strip currency symbols and convert to numeric
    orders['Checkout Price'] = orders['Checkout Price'].str.replace('£', '').astype(float)
    orders['VAT Amount'] = orders['VAT Amount'].str.replace('£', '').astype(float)

    # Creating the necessary columns for Xero template
    xero_data = pd.DataFrame(columns=[
        '*ContactName', '*InvoiceNumber', '*InvoiceDate', '*DueDate', '*Quantity', '*UnitAmount', '*AccountCode',
        '*TaxType'
    ])

    # Processing each order to generate Xero import rows
    for index, row in orders.iterrows():
        # Create the main row
        unit_amount = row['VAT Amount'] * 6 if row['VAT == 1/6 Checkout Price'] == 0 else row['Checkout Price']

        main_row = {
            '*ContactName': row['Supplier'],
            '*InvoiceNumber': row['Order ID'],
            '*InvoiceDate': row['Order Date'],
            '*DueDate': row['Order Date'],
            '*Quantity': 1,
            '*UnitAmount': unit_amount,
            '*AccountCode': 'Stock',
            '*TaxType': '20% (VAT on Expenses)'
        }

        xero_data = pd.concat([xero_data, pd.DataFrame([main_row])], ignore_index=True)

        # If VAT == 1/6 Checkout Price is 0, create a discount row
        if row['VAT == 1/6 Checkout Price'] == 0:
            discount_amount = unit_amount - row['Checkout Price']

            discount_row = {
                '*ContactName': row['Supplier'],
                '*InvoiceNumber': row['Order ID'],
                '*InvoiceDate': row['Order Date'],
                '*DueDate': row['Order Date'],
                '*Quantity': 1,
                '*UnitAmount': -discount_amount,
                '*AccountCode': 'Discounts',
                '*TaxType': 'No VAT'
            }

            xero_data = pd.concat([xero_data, pd.DataFrame([discount_row])], ignore_index=True)

    # Saving the dataframe to a new CSV file
    processed_filename = 'xero_bills_export.csv'
    processed_filepath = os.path.join(PROCESSED_FOLDER, processed_filename)
    xero_data.to_csv(processed_filepath, index=False)

    return processed_filepath


if __name__ == '__main__':
    app.run(debug=True)
