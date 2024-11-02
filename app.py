from flask import Flask, request, redirect, render_template, send_file, send_from_directory
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
    orders_file = request.files.get('orders_file')
    cancellations_file = request.files.get('cancellations_file')
    date_format = request.form.get('date_format')

    if not orders_file or orders_file.filename == '':
        return redirect('/')

    orders_filepath = os.path.join(app.config['UPLOAD_FOLDER'], orders_file.filename)
    orders_file.save(orders_filepath)
    orders_processed_filepath = process_orders(orders_filepath, date_format)

    # Process cancellations if the file is provided
    if cancellations_file and cancellations_file.filename != '':
        cancellations_filepath = os.path.join(app.config['UPLOAD_FOLDER'], cancellations_file.filename)
        cancellations_file.save(cancellations_filepath)
        cancellations_processed_filepath = process_cancellations(cancellations_filepath, date_format)
        return send_from_directory(PROCESSED_FOLDER, cancellations_processed_filepath, as_attachment=True)

    return send_from_directory(PROCESSED_FOLDER, orders_processed_filepath, as_attachment=True)


def process_orders(filepath, date_format):
    # Process orders CSV file as you already have it.
    orders = pd.read_csv(filepath)
    # Existing processing logic for orders...
    processed_filename = 'xero_bills_export.csv'
    processed_filepath = os.path.join(PROCESSED_FOLDER, processed_filename)
    orders.to_csv(processed_filepath, index=False)
    return processed_filename


def process_cancellations(filepath, date_format):
    cancellations = pd.read_csv(filepath)
    # Process cancellations CSV file similar to the code you have.

    cancellations['Checkout Price (from Order) (from Orderline)'] = cancellations[
        'Checkout Price (from Order) (from Orderline)'].str.replace('£', '').astype(float)
    cancellations['VAT Amount (from Order) (from Orderline)'] = cancellations[
        'VAT Amount (from Order) (from Orderline)'].str.replace('£', '').astype(float)

    xero_refund_data = pd.DataFrame(columns=[
        '*ContactName', '*InvoiceNumber', '*InvoiceDate', '*DueDate', '*Quantity', '*UnitAmount', '*AccountCode',
        '*TaxType'
    ])

    cancellations_filtered = cancellations[
        cancellations['Order fully cancelled (from Order) (from Orderline)'] == 1].drop_duplicates(
        subset=['Order (from Orderline)'])

    for index, row in cancellations_filtered.iterrows():
        unit_amount = row['VAT Amount (from Order) (from Orderline)'] * 6 if row[
                                                                                 'VAT == 1/6 Checkout Price (from Order) (from Orderline)'] == 0 else \
            row['Checkout Price (from Order) (from Orderline)']

        main_row = {
            '*ContactName': row['Supplier (from Order) (from Orderline)'],
            '*InvoiceNumber': row['Credit Note Number'],
            '*InvoiceDate': row['Cancellation/Refund Date'],
            '*DueDate': row['Cancellation/Refund Date'],
            '*Quantity': 1,
            '*UnitAmount': -unit_amount,
            '*AccountCode': 'Stock',
            '*TaxType': '20% (VAT on Expenses)'
        }

        xero_refund_data = pd.concat([xero_refund_data, pd.DataFrame([main_row])], ignore_index=True)

        if row['VAT == 1/6 Checkout Price (from Order) (from Orderline)'] == 0:
            discount_amount = unit_amount - row['Checkout Price (from Order) (from Orderline)']
            discount_row = {
                '*ContactName': row['Supplier (from Order) (from Orderline)'],
                '*InvoiceNumber': row['Credit Note Number'],
                '*InvoiceDate': row['Cancellation/Refund Date'],
                '*DueDate': row['Cancellation/Refund Date'],
                '*Quantity': 1,
                '*UnitAmount': discount_amount,
                '*AccountCode': 'Discounts',
                '*TaxType': 'No VAT'
            }
            xero_refund_data = pd.concat([xero_refund_data, pd.DataFrame([discount_row])], ignore_index=True)

    processed_filename = 'xero_refunds_export.csv'
    processed_filepath = os.path.join(PROCESSED_FOLDER, processed_filename)
    xero_refund_data.to_csv(processed_filepath, index=False)

    return processed_filename


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
