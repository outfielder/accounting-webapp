from flask import Flask, request, redirect, render_template, send_file
import pandas as pd
import os
from datetime import datetime

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(PROCESSED_FOLDER):
    os.makedirs(PROCESSED_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/')
def home():
    return render_template('upload.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect('/')

    file = request.files['file']
    date_format = request.form.get('date_format')

    if file.filename == '':
        return redirect('/')

    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        processed_filepath = process_file(filepath, date_format)
        return send_file(processed_filepath, as_attachment=True)


def process_file(filepath, date_format):
    orders = pd.read_csv(filepath)

    orders.columns = ['Order ID', 'Order Date', 'Invoice', 'Checkout Price', 'VAT Amount', 'Supplier',
                      'VAT == 1/6 Checkout Price']

    orders['Checkout Price'] = orders['Checkout Price'].str.replace('£', '').astype(float)
    orders['VAT Amount'] = orders['VAT Amount'].str.replace('£', '').astype(float)

    # Define the date conversion format based on user input
    input_date_format = '%d/%m/%Y' if date_format == 'dd/mm/yyyy' else '%m/%d/%Y'
    output_date_format = '%d/%m/%Y' if date_format == 'mm/dd/yyyy' else input_date_format

    # Convert dates based on the selected input format
    orders['Order Date'] = orders['Order Date'].apply(lambda x: datetime.strptime(x, input_date_format).strftime(output_date_format))

    xero_data = pd.DataFrame(columns=[
        '*ContactName', '*InvoiceNumber', '*InvoiceDate', '*DueDate', '*Quantity', '*UnitAmount', '*AccountCode',
        '*TaxType'
    ])

    for index, row in orders.iterrows():
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

    processed_filename = 'xero_bills_export.csv'
    processed_filepath = os.path.join(PROCESSED_FOLDER, processed_filename)
    xero_data.to_csv(processed_filepath, index=False)

    return processed_filepath


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
