'''
Created on Jul 10, 2018

@author: erins
'''
import unittest
import devodataprocessing as devo
import pandas as pd
import numpy as np
from platetemplates import generictemplate
import enum


class Test(unittest.TestCase):
    '''
    Tests devo assay raw data parsing methods
    '''

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testGetRawData(self):
        self.assertIsNone(
            devo.getrawdata('random file name.xlsx'),
            'Calling function on non-existent file did not throw an error')
        self.assertIsNone(
            devo.getrawdata('testing'),
            'Calling function on wrong filetype did not throw an error')

    def testParseLocations(self):
        df_input = pd.DataFrame({
            'Location': ['Plate 1 - Well F4', 'Plate 2 - Well C10', 'Plate 3 - Well H7']
        })
        df_expected_output = pd.DataFrame({
            'Location': ['Plate 1 - Well F4', 'Plate 2 - Well C10', 'Plate 3 - Well H7'],
            'Plate': [1, 2, 3],
            'Row': ['F', 'C', 'H'],
            'Column': [4, 10, 7]
        })
        df_actual_output = devo.parselocations(df_input)
        self.assertTrue(
            'Plate' in df_actual_output.columns,
            'Plate does not exist as a column after parsing location strings')
        self.assertTrue(
            'Row' in df_actual_output.columns,
            'Row does not exist as a column after parsing location strings')
        self.assertTrue(
            'Column' in df_actual_output.columns,
            'Column does not exist as a column after parsing location strings')
        self.assertEqual(list(df_actual_output.Plate),
                         [1, 2, 3],
                         'Plate numbers were not parsed correctly')
        self.assertEqual(list(df_actual_output.Row),
                         ['F', 'C', 'H'],
                         'Row letters were not parsed correctly')
        self.assertEqual(list(df_actual_output.Column),
                         [4, 10, 7],
                         'Column numbers were not parsed correctly')
        pd.testing.assert_frame_equal(
            df_actual_output,
            df_expected_output,
            'Dataframe did not update properly when parsing location strings')

    def testPlateLocation(self):
        self.assertEqual(devo.getplate("Plate 1 - Well A12"),
                         1, "Plate was not parsed correctly")

    def testColumnLocation(self):
        # Test single digit column number
        self.assertEqual(devo.getcolumn("Plate 1 - Well A1"),
                         1, "Column not parsed correctly")
        # Test double digit column number
        self.assertEqual(devo.getcolumn("Plate 1 - Well A12"),
                         12, "Column not parsed correctly")

    def testRowLocation(self):
        self.assertEqual(devo.getrow("Plate 1 - Well A1"),
                         "A", "Row not parsed correctly")

    def testFixSampleBarcodes(self):
        df_input = pd.DataFrame({
            'Sample Barcode': ['1', '100', 'qc1']
        })
        df_expected_output = pd.DataFrame({
            'Sample Barcode': [1, 100, 'QC1']
        })
        df_actual_output = devo.fixbarcodes(df_input)
        pd.testing.assert_frame_equal(
            df_actual_output,
            df_expected_output,
            "Dataframe Sample Barcode column not updated properly")
        self.assertEqual(
            list(
                df_actual_output['Sample Barcode']), [
                1, 100, 'QC1'], 'Values in Sample Barcode column did not update properly')

    def testFixDataNumbers(self):
        df_input = pd.DataFrame({
            'AEB': ['0.007', 'NaN', ''],
            'Concentration': ['12.3', 'NaN', '']
        })
        df_expected_output = pd.DataFrame({
            'AEB': [0.007, np.nan, np.nan],
            'Concentration': [12.3, np.nan, np.nan]
        })
        df_actual_output = devo.fixdatanumbers(df_input)
        pd.testing.assert_frame_equal(
            df_actual_output,
            df_expected_output,
            'Dataframe did not update properly when converting AEB and Concentration')

    def testCalculateConentrationInFgPerMl(self):
        df_input = pd.DataFrame({
            'Concentration': [0.001, 0.02, 0.3, 4, 50, 500, np.nan]
        })
        df_expected_output = pd.DataFrame({
            'Concentration': [0.001, 0.02, 0.3, 4, 50, 500, np.nan],
            'Concentration (fg/ml)': [1.0, 20.0, 300.0, 4000, 50000, 500000, np.nan]
        })
        df_actual_output = devo.calculateconcentrationinfg(df_input)
        pd.testing.assert_frame_equal(
            df_actual_output,
            df_expected_output,
            "Dataframe did not update properly when converting Concentration to fg/ml")

    def testPlateTemplate(self):
        df_input = pd.DataFrame()
        df_input['Column'] = pd.Series([], dtype=object)

        rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        for row in rows:
            for col in range(1, 13):
                df_input = df_input.append(
                    {'Row': row, 'Column': col}, ignore_index=True)

        feeders = {'Axis': 'Column',
                   **dict.fromkeys([1, 2, 3, 4, 5, 6], 'FeederOne'),
                   **dict.fromkeys([7, 8, 9, 10, 11, 12], 'FeederTwo')}

        replicates = {'Axis': 'Column'}
        for x in range(1, 7):
            replicates[int(x)] = int(x)
            replicates[int(x) + 6] = int(x)

        dilutions = {'Axis': 'Row',
                     **dict.fromkeys(['A', 'E'], 0.5),
                     **dict.fromkeys(['B', 'F'], 0.1),
                     **dict.fromkeys(['C', 'G'], 0.05),
                     **dict.fromkeys(['D', 'H'], 0.025)}

        print(generictemplate(df_input, dilutions, feeders, replicates))


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
