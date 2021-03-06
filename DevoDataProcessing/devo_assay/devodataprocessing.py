'''
Created on Jul 23, 2018

@author: erins
'''
#pylint: disable=invalid-name
import re
from functools import reduce
import pandas as pd
import pyexcel
from pyexcel.exceptions import FileTypeNotSupported
from platetemplates import template01
from platetemplates import template02


def getrawdata(filename, headerrows=5):
    '''
    Gets raw data from Quanterix .xls export file
    Generates a pandas dataframe for the raw data
    Removes extraneous rows that preceed the headers row
    Removes extraneous columns that are not needed for data analysis
    Returns the dataframe for the raw data

    Parameters:
    ----------
    filename: name of file containing the raw data output from the Simoa instrument.
        Should be in the format .xls.
    headerrows: number of rows to remove that preceed the header rows
        (containing labels for the data columns)

    Returns:
    ----------
    dataframe containing all raw data from the data file
    '''

    '''
    Retrieve the raw data and store in dictionary
    Remove all extraneous rows as indicated by the headerrows parameter
    Use dictionary to create the pandas raw data dataframe
    '''
    try:
        raw_data = pyexcel.get_dict(
            file_name=filename,
            name_columns_by_row=headerrows)
    except (FileTypeNotSupported, FileNotFoundError):
        return None
    raw_data = {k: raw_data[k][headerrows:] for k in raw_data}
    data_df = pd.DataFrame(raw_data)

    '''
    Remove unnecessary columns
    '''
    columns_to_keep = [
        'Sample Barcode',
        'Location',
        'Sample Type',
        'Batch Name',
        'AEB',
        'Concentration',
        'Flags']

    for column in data_df.columns.values:
        if column not in columns_to_keep:
            try:
                data_df = data_df.drop(column, axis=1)
            except KeyError:
                continue

    return data_df


def parselocations(data):
    '''
    Parses out location information for each row of data into 3 distinct
        pieces of information in their own data columns:
        - Plate number (as integer)
        - Row letter (as uppercase A-H)
        - Column number (as integer)
    Location is in format {Plate # - Well [A-H][1-12]}

    Parameters:
    ----------
    data - pandas dataframe containing raw data from simoa file
        (data has been parsed from getrawdata()

    Returns:
    ---------
    Updated dataframe with locations parsed as indicated above
    '''
    data = data.assign(
        Plate=data.Location.apply(getplate),
        Row=data.Location.apply(getrow),
        Column=data.Location.apply(getcolumn)
    )
    return data


def getplate(location):
    '''
    Reads a string in the format "Plate # - Well [A-H][1-12]"
    Returns the plate number as an integer

    Parameters:
    ----------
    location: string in the format "Plate # - Well [A-H][1-12]"

    Returns:
    ----------
    The number following the word "Plate" as an integer
    '''
    return int(location.split(' ')[1])


def getrow(location):
    '''
    Reads a string in the format "Plate # - Well [A-H][1-12]"
    Returns the row letter as a string

    Parameters:
    ----------
    location: string in the format "Plate # - Well [A-H][1-12]"

    Returns:
    ----------
    The letter following the word "Well" as a string
    '''
    return location.split(' ')[4][0]


def getcolumn(location):
    '''
    Reads a string in the format "Plate # - Well [A-H][1-12]"
    Returns the column number as an integer

    Parameters:
    ----------
    location: string in the format "Plate # - Well [A-H][1-12]"

    Returns:
    ----------
    The number following the row letter as an integer
    '''
    return int(location.split(' ')[4][1:])


def fixbarcodes(data):
    '''
    Change Sample Barcode values to numeric values
    Any text (such as calibrator barcodes or QC barcodes) will be changed to uppercase
    to facilitate handling later

    Parameters:
    ----------
    data - pandas dataframe containing a column called 'Sample Barcode'

    Return:
    ----------
    dataframe containing the updated 'Sample Barcode' column
    '''
    data['Sample Barcode'] = data['Sample Barcode'].apply(
        lambda x: int(x) if re.match(r'\d+', x) else x.upper())
    return data


def fixdatanumbers(data):
    '''
    Change AEB and Concentration values to numeric values
    Any NaN or '' values are set to np.nan

    Parameters:
    ----------
    data - pandas dataframe containing two columns with
    numeric values in string format: 'AEB', 'Concentration'

    Return:
    ----------
    dataframe containing the updated 'AEB' and 'Concentration' columns
    '''
    data[['AEB', 'Concentration']] = data[['AEB', 'Concentration']].apply(
        pd.to_numeric, errors='coerce')

    return data


def calculateconcentrationinfg(data):
    '''
    Convert Concentration, which is in pg/ml, to fg/ml

    Parameters:
    ----------
    data - pandas dataframe containing a column with concentration values in pg/ml

    Returns:
    ----------
    dataframe containing a new column 'Concentration (fg/ml)'
    '''
    data['Concentration (fg/ml)'] = data['Concentration'].apply(lambda x: x * 1000.0)

    return data


def extractbatches(data):
    '''
    For each batch name in the raw data, create a batch object
    with only the data associated with that batch name

    Paramaters:
    -----------
    data - pandas dataframe containing cleaned-up raw data

    Returns:
    ----------
    A list of Batch objects containing batch name and raw data associated
    only with that batch
    '''
    return [Batch(batch_name, data[data['Batch Name'] == batch_name])
            for batch_name in data['Batch Name'].unique()]


# Work on processing batches:
    # Experiment Number (PH or BD)
    # QC information
    # Standard information (if applicable)
    # Highest Value
    # Handle flags
    # Per plate:
    #    Day,
    #    Condition,
    #    Dilutions
    #        nums
    #        rows vs cols?
    #    Feeders
    #        which ones
    #        where on plate?
    #    Replicates/dilution/feeder
    #        rows/cols (same as dilutions)


class Batch(object):
    '''
    Batch() stores the state of one batch from the Simoa.
    A single batch has the following information:
    - Date
    - Batch Name
    - Set of QC samples
    - Set of Standards (optional)
    - Lot number for QC/Standards
    - Maximum Concentration (fg/ml) value
    - Raw Data for entire batch
    - One or more plates (see Plate())
    '''

    def __init__(self, name, data):
        '''
        Constructs a Batch object setting name and raw data.  From the raw data,
        QC data, Standards data and highest Concentration in fg/ml are determined.

        A list of plates and corresponding raw data for each plate are also
        extracted and stored in the Batch object.

        TODO: The lot and date for the batch are also determined.

        Parameters:
        ----------
        name - batch name associated with the data
        data - pandas dataframe containing all raw data associated with batch name
        '''
        self.name = name
        self.data = data
        self.lot = None
        self.date = self.setdate()
        self.qcs = self.setqcs()
        self.standards = self.setstandards()
        self.highestvalue = self.sethighestvalue()
        self.plates = self.setplates()

    def setdate(self):
        ''' Sets the date based on the batch name
        TODO: Not yet implemented
        '''
        pass

    def setqcs(self):
        '''
        Handles the QC Values from the data
        Validates them?
        TODO: Not yet implemented
        '''
        pass

    def setstandards(self):
        '''
        Handles the Standard Calibrators from the data
        TODO: Not yet implemented
        Might use the data for over time analysis and store it elsewhere
        '''
        pass

    def setlot(self, lot):
        '''
        Lot number determines what values the QCs are validated against
        TODO: Not yet implemented
        Need to determine where I will store information for each QC lot
        '''
        self.lot = lot

    def sethighestvalue(self):
        '''
        Returns the highest concentration of p24 in fg/ml
        Value is used to upated reported result for samples above the ULOQ
        '''
        return self.data['Concentration (fg/ml)'].max()

    def setplates(self):
        '''
        Parses out each plate found in the Batch and creates a Plate object
        passing to it the batch name, plate number and all data associated
        with that plate
        TODO: Should I just pass in the Batch and store it with it?
        '''
        return [Plate(self.name, plate_num, self.data[self.data['Plate'] == plate_num])
                for plate_num in self.data['Plate'].unique()]

    def __str__(self):
        '''
        TODO: Work in progress, changes as needed
        '''
        return f'Name: {self.name}\nData: {self.data}'


class Plate(object):
    '''
    Plate() stores the state of a single plate in a given Simoa Batch()
    Each plate has the following information:
    - Batch Name
    - Experiment Name
    - Timepoint Day
    - LRA Condition
    - Dilutions
    - Location of Dilutions (rows versus columns)
    - Feeder Condition(s)
    - Location of Feeder Condition(s)
    - Number of Replicates per dilution/feeder combination
    - Raw Data for entire plate
    '''

    def __init__(self, batch, plate_num, data):
        '''
        Constructs a single Plate from a Simoa Batch.  Extracts specific information
        about the plate based on information from the Batch Name.
        '''
        self.condition = None
        self.timepoint = None
        self.experiment = None
        self.template = None
        self.batch = batch
        self.plate_num = plate_num
        self.data = data

    def applytemplate(self, dilutions, feeders, replicates):
        '''
        Uses a template to apply the appropriate dilution,
        feeder and replicate to each row of the data

        Parameters:
        ----------
        data - pandas dataframe with one plate-worth of data
        dilutions - a dictionary in the following format:
            {'Axis': 'Row' or 'Column', ...}
            Remainder of dictionary lists which rows/columns correspond to a specific dilution
        feeders - a dictionary in the following format:
            {'Axis': 'Row' or 'Column', ...}
            Remainder of dictionary lists which rows/columns correspond to a specific feeder
        replicates -a dictionary in the following format:
            {'Axis': 'Row' or 'Column', ...}
            Remainder of dictionary lists which rows/columns correspond to a specific replicate

        Returns:
        ----------
        pandas data frame containing the updated plate data containing the assigned dilutions,
        feeders, and replicates
        '''
        # Copy data to prevent SetWithCopyWarning
        data = self.data.copy()

        # Assign Dilutions
        data['Dilution'] = data[dilutions['Axis']].apply(
            lambda x: dilutions[x] if x in list(dilutions.keys())[1:] else None)

        # Assign Feeders
        data['Feeders'] = data[feeders['Axis']].apply(
            lambda x: feeders[x] if x in list(feeders.keys())[1:] else None)

        # Assign Replicates
        data['Replicate'] = data[replicates['Axis']].apply(
            lambda x: replicates[x] if x in list(replicates.keys())[1:] else None)

        self.data = data

    def __str__(self):
        return f'Name: {self.batch}\nPlate Number: {self.plate_num}'


def call(x, f):
    ''' Helper function for calling functions using reduce
    '''
    return f(x)


if __name__ == '__main__':
    df_data = pd.DataFrame
    filename = '../test_files/2018-06-21_20-37-11_-123.xls'
    df_data = getrawdata(filename)
    funcs = [
        parselocations,
        fixbarcodes,
        fixdatanumbers,
        calculateconcentrationinfg]
    df_data = reduce(call, funcs, df_data)
    batches = extractbatches(df_data)
    print(batches[0].plates[0].applytemplate(template01)['Dilution'])
