'''
Created on 21/02/2013

@author: u76345
'''
import os
import sys
import logging
import re
import numpy
from datetime import datetime, time
from osgeo import gdal, gdalconst
from time import sleep

from stacker import Stacker
from vrt2bin import vrt2bin
from log_multiline import log_multiline
from edit_envi_hdr import edit_envi_hdr


# Add stats path for Joshua Sixsmith's statistical analysis code
sys.path.append(os.path.join(os.path.dirname(__file__), 'stats'))              
import temporal_stats_numexpr_module

SCALE_FACTOR = 10000
NaN = numpy.float32(numpy.NaN)

# Set top level standard output 
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(console_formatter)

logger = logging.getLogger(__name__)
if not logger.level:
    logger.setLevel(logging.DEBUG) # Default logging level for all modules
    logger.addHandler(console_handler)
                
class IndexStacker(Stacker):
    """ Subclass of Stacker
    Used to implement specific functionality to create stacks of derived datasets.
    """
    def derive_datasets(self, input_dataset_dict, stack_output_info, tile_type_info):
        """ Overrides abstract function in stacker class. Called in Stacker.stack_derived() function. 
        Creates PQA-masked NDVI stack
        
        Arguments:
            nbar_dataset_dict: Dict keyed by processing level (e.g. ORTHO, NBAR, PQA, DEM)
                containing all tile info which can be used within the function
                A sample is shown below (including superfluous band-specific information):
                
{
'NBAR': {'band_name': 'Visible Blue',
    'band_tag': 'B10',
    'end_datetime': datetime.datetime(2000, 2, 9, 23, 46, 36, 722217),
    'end_row': 77,
    'level_name': 'NBAR',
    'nodata_value': -999L,
    'path': 91,
    'satellite_tag': 'LS7',
    'sensor_name': 'ETM+',
    'start_datetime': datetime.datetime(2000, 2, 9, 23, 46, 12, 722217),
    'start_row': 77,
    'tile_layer': 1,
    'tile_pathname': '/g/data/v10/datacube/EPSG4326_1deg_0.00025pixel/LS7_ETM/150_-025/2000/LS7_ETM_NBAR_150_-025_2000-02-09T23-46-12.722217.tif',
    'x_index': 150,
    'y_index': -25},
'ORTHO': {'band_name': 'Thermal Infrared (Low Gain)',
     'band_tag': 'B61',
     'end_datetime': datetime.datetime(2000, 2, 9, 23, 46, 36, 722217),
     'end_row': 77,
     'level_name': 'ORTHO',
     'nodata_value': 0L,
     'path': 91,
     'satellite_tag': 'LS7',
     'sensor_name': 'ETM+',
     'start_datetime': datetime.datetime(2000, 2, 9, 23, 46, 12, 722217),
     'start_row': 77,
     'tile_layer': 1,
     'tile_pathname': '/g/data/v10/datacube/EPSG4326_1deg_0.00025pixel/LS7_ETM/150_-025/2000/LS7_ETM_ORTHO_150_-025_2000-02-09T23-46-12.722217.tif',
     'x_index': 150,
     'y_index': -25},
'PQA': {'band_name': 'Pixel Quality Assurance',
    'band_tag': 'PQA',
    'end_datetime': datetime.datetime(2000, 2, 9, 23, 46, 36, 722217),
    'end_row': 77,
    'level_name': 'PQA',
    'nodata_value': None,
    'path': 91,
    'satellite_tag': 'LS7',
    'sensor_name': 'ETM+',
    'start_datetime': datetime.datetime(2000, 2, 9, 23, 46, 12, 722217),
    'start_row': 77,
    'tile_layer': 1,
    'tile_pathname': '/g/data/v10/datacube/EPSG4326_1deg_0.00025pixel/LS7_ETM/150_-025/2000/LS7_ETM_PQA_150_-025_2000-02-09T23-46-12.722217.tif,
    'x_index': 150,
    'y_index': -25}
}                
                
        Arguments (Cont'd):
            stack_output_info: dict containing stack output information. 
                Obtained from stacker object. 
                A sample is shown below
                
stack_output_info = {'x_index': 144, 
                      'y_index': -36,
                      'stack_output_dir': '/g/data/v10/tmp/ndvi',
                      'start_datetime': None, # Datetime object or None
                      'end_datetime': None, # Datetime object or None 
                      'satellite': None, # String or None 
                      'sensor': None} # String or None 
                      
        Arguments (Cont'd):
            tile_type_info: dict containing tile type information. 
                Obtained from stacker object (e.g: stacker.tile_type_dict[tile_type_id]). 
                A sample is shown below
                
{'crs': 'EPSG:4326',
    'file_extension': '.tif',
    'file_format': 'GTiff',
    'format_options': 'COMPRESS=LZW,BIGTIFF=YES',
    'tile_directory': 'EPSG4326_1deg_0.00025pixel',
    'tile_type_id': 1L,
    'tile_type_name': 'Unprojected WGS84 1-degree at 4000 pixels/degree',
    'unit': 'degree',
    'x_origin': 0.0,
    'x_pixel_size': Decimal('0.00025000000000000000'),
    'x_pixels': 4000L,
    'x_size': 1.0,
    'y_origin': 0.0,
    'y_pixel_size': Decimal('0.00025000000000000000'),
    'y_pixels': 4000L,
    'y_size': 1.0}
                            
        Function must create one or more GDAL-supported output datasets. Useful functions in the
        Stacker class include Stacker.get_pqa_mask(), but it is left to the coder to produce exactly
        what is required for a single slice of the temporal stack of derived quantities.
            
        Returns:
            output_dataset_info: Dict keyed by stack filename
                containing metadata info for GDAL-supported output datasets created by this function.
                Note that the key(s) will be used as the output filename for the VRT temporal stack
                and each dataset created must contain only a single band. An example is as follows:
{'/g/data/v10/tmp/ndvi/NDVI_stack_150_-025.vrt': 
    {'band_name': 'Normalised Differential Vegetation Index with PQA applied',
    'band_tag': 'NDVI',
    'end_datetime': datetime.datetime(2000, 2, 9, 23, 46, 36, 722217),
    'end_row': 77,
    'level_name': 'NDVI',
    'nodata_value': None,
    'path': 91,
    'satellite_tag': 'LS7',
    'sensor_name': 'ETM+',
    'start_datetime': datetime.datetime(2000, 2, 9, 23, 46, 12, 722217),
    'start_row': 77,
    'tile_layer': 1,
    'tile_pathname': '/g/data/v10/tmp/ndvi/LS7_ETM_NDVI_150_-025_2000-02-09T23-46-12.722217.tif',
    'x_index': 150,
    'y_index': -25}
}
        """
        assert type(input_dataset_dict) == dict, 'nbar_dataset_dict must be a dict'
                
        # Define lookup dicts
        dtype = {'NDVI' : gdalconst.GDT_Int16,
                 'EVI' : gdalconst.GDT_Int16,
                 'NDSI' : gdalconst.GDT_Int16,
                 'NDMI' : gdalconst.GDT_Int16,
                 'SLAVI' : gdalconst.GDT_Float32,
                 'SATVI' : gdalconst.GDT_Int16,
                 'WATER' : gdalconst.GDT_Byte}

        no_data_value = {'NDVI' : -32768,
                 'EVI' : -32768,
                 'NDSI' : -32768,
                 'NDMI' : -32768,
                 'SLAVI' : numpy.nan,
                 'SATVI' : -32768,
                 'WATER' : -1}
    
        log_multiline(logger.debug, input_dataset_dict, 'nbar_dataset_dict', '\t')    
       
        # Test function to copy ORTHO & NBAR band datasets with pixel quality mask applied
        # to an output directory for stacking

        output_dataset_dict = {}
        nbar_dataset_info = input_dataset_dict['NBAR'] # Only need NBAR data for NDVI
        #thermal_dataset_info = input_dataset_dict['ORTHO'] # Could have one or two thermal bands
        
        nbar_dataset_path = nbar_dataset_info['tile_pathname']
        
        # Get a boolean mask from the PQA dataset (use default parameters for mask and dilation)
        pqa_mask = self.get_pqa_mask(input_dataset_dict['PQA']['tile_pathname']) 
        
        nbar_dataset = gdal.Open(nbar_dataset_path)
        assert nbar_dataset, 'Unable to open dataset %s' % nbar_dataset
        
        band_array = None;
        for output_tag in ['NDVI', 'EVI', 'NDSI', 'NDMI', 'SLAVI', 'SATVI', 'WATER']: # List of outputs to generate from each file
            # TODO: Make the stack file name reflect the date range                    
            output_stack_path = os.path.join(self.output_dir, 
                                             re.sub('\+', '', '%s_%+04d_%+04d' % (output_tag,
                                                                                   stack_output_info['x_index'],
                                                                                    stack_output_info['y_index'])))
                                                                                    
            if stack_output_info['start_datetime']:
                output_stack_path += '_%s' % stack_output_info['start_datetime'].strftime('%Y%m%d')
            if stack_output_info['end_datetime']:
                output_stack_path += '_%s' % stack_output_info['end_datetime'].strftime('%Y%m%d')
                
            output_stack_path += '_pqa.vrt'
            
            output_tile_path = os.path.join(self.output_dir, re.sub('\.\w+$', tile_type_info['file_extension'],
                                                                    re.sub('NBAR', 
                                                                           output_tag,
                                                                           os.path.basename(nbar_dataset_path)
                                                                           )
                                                                   )
                                           )
                
            # Copy metadata for eventual inclusion in stack file output
            # This could also be written to the output tile if required
            output_dataset_info = dict(nbar_dataset_info)
            output_dataset_info['tile_pathname'] = output_tile_path # This is the most important modification - used to find tiles to stack
            output_dataset_info['band_name'] = '%s with PQA mask applied' % output_tag
            output_dataset_info['band_tag'] = '%s-PQA' % output_tag
            output_dataset_info['tile_layer'] = 1
            
            #TODO: Check this with Josh
            #if no_data_value[output_tag] is NaN:
            #    output_dataset_info['nodata_value'] = None # Can't SetNoDataValue using NaN
            #else:
            output_dataset_info['nodata_value'] = no_data_value[output_tag]

            # Check for existing, valid file
            if self.refresh or not os.path.exists(output_tile_path) or not gdal.Open(output_tile_path):

                if self.lock_object(output_tile_path): # Test for concurrent writes to the same file
                    # Read whole nbar_dataset into one array. 
                    # 62MB for float32 data should be OK for memory depending on what else happens downstream
                    if band_array is None:
                        # Convert to float32 for arithmetic
                        band_array = nbar_dataset.ReadAsArray().astype(numpy.float32)
                
                    gdal_driver = gdal.GetDriverByName(tile_type_info['file_format'])
                    #output_dataset = gdal_driver.Create(output_tile_path, 
                    #                                    nbar_dataset.RasterXSize, nbar_dataset.RasterYSize,
                    #                                    1, nbar_dataset.GetRasterBand(1).DataType,
                    #                                    tile_type_info['format_options'].split(','))
                    output_dataset = gdal_driver.Create(output_tile_path, 
                                                        nbar_dataset.RasterXSize, nbar_dataset.RasterYSize,
                                                        1, dtype[output_tag],
                                                        tile_type_info['format_options'].split(','))
                    assert output_dataset, 'Unable to open output dataset %s'% output_dataset                                   
                    output_dataset.SetGeoTransform(nbar_dataset.GetGeoTransform())
                    output_dataset.SetProjection(nbar_dataset.GetProjection()) 
        
                    output_band = output_dataset.GetRasterBand(1)
        
                    # Calculate each output here
                    # Remember band_array indices are zero-based
                    if output_tag == 'NDVI':
                        data_array = numpy.true_divide(band_array[3] - band_array[2], band_array[3] + band_array[2]) * SCALE_FACTOR
                    elif output_tag == 'EVI':
                        data_array = 25000 * ((band_array[3] - band_array[2]) / (band_array[3] + (60000 * band_array[2]) - (75000 * band_array[0]) + 10000))
                    elif output_tag == 'NDSI':   
                        data_array = numpy.true_divide(band_array[2] - band_array[4], band_array[2] + band_array[4]) * SCALE_FACTOR
                    elif output_tag == 'NDMI':
                        data_array = numpy.true_divide(band_array[3] - band_array[4], band_array[3] + band_array[4]) * SCALE_FACTOR
                    elif output_tag == 'SLAVI':
                        data_array = numpy.true_divide(band_array[3], (band_array[2] + band_array[4]))
                    elif output_tag == 'SATVI':
                        print 'nbar_dataset_path: ', nbar_dataset_path
                        print 'band_array[:,1747,775]: ', band_array[:,1747,775]
                        data_array = ((band_array[4] - band_array[2]) / (band_array[4] + band_array[2] + 5000)) *15000 - (band_array[5]/2)
                    elif output_tag == 'WATER':
                        data_array = numpy.zeros(band_array[0].shape, dtype=numpy.byte)
                        #TODO: Call water analysis code here
                    else:
                        raise Exception('Invalid operation')
                                        
                    if no_data_value[output_tag]:
                        if output_tag == 'SATVI':
                            print 'before pq application'
                            print 'nbar_dataset_path: ', nbar_dataset_path
                            print 'data_array[1747,775]: ', data_array[1747,775]
                        self.apply_pqa_mask(data_array, pqa_mask, no_data_value[output_tag])
                        if output_tag == 'SATVI':
                            print 'after pq application'
                            print 'nbar_dataset_path: ', nbar_dataset_path
                            print 'data_array[1747,775]: ', data_array[1747,775]
                    
                    output_band.WriteArray(data_array)
                    output_band.SetNoDataValue(output_dataset_info['nodata_value'])
                    output_band.FlushCache()
                    
                    # This is not strictly necessary - copy metadata to output dataset
                    output_dataset_metadata = nbar_dataset.GetMetadata()
                    if output_dataset_metadata:
                        output_dataset.SetMetadata(output_dataset_metadata) 
                        log_multiline(logger.debug, output_dataset_metadata, 'output_dataset_metadata', '\t')    
                    
                    output_dataset.FlushCache()
                    self.unlock_object(output_tile_path)
                    logger.info('Finished writing dataset %s', output_tile_path)
                else:
                    logger.info('Skipped locked dataset %s', output_tile_path)
                    sleep(5) #TODO: Find a nicer way of dealing with contention for the same output tile
                    
            else:
                logger.info('Skipped existing dataset %s', output_tile_path)
        
            output_dataset_dict[output_stack_path] = output_dataset_info
#                    log_multiline(logger.debug, output_dataset_info, 'output_dataset_info', '\t')    

        log_multiline(logger.debug, output_dataset_dict, 'output_dataset_dict', '\t')    
        # NDVI dataset processed - return info
        return output_dataset_dict
    

if __name__ == '__main__':
    def assemble_stack(index_stacker):    
        """
        returns stack_info_dict - a dict keyed by stack file name containing a list of tile_info dicts
        """
        def date2datetime(input_date, time_offset=time.min):
            if not input_date:
                return None
            return datetime.combine(input_date, time_offset)
            
        stack_info_dict = index_stacker.stack_derived(x_index=index_stacker.x_index, 
                             y_index=index_stacker.y_index, 
                             stack_output_dir=index_stacker.output_dir, 
                             start_datetime=date2datetime(index_stacker.start_date, time.min), 
                             end_datetime=date2datetime(index_stacker.end_date, time.max), 
                             satellite=index_stacker.satellite, 
                             sensor=index_stacker.sensor)
        
        log_multiline(logger.debug, stack_info_dict, 'stack_info_dict', '\t')
        
        logger.info('Finished creating %d temporal stack files in %s.', len(stack_info_dict), index_stacker.output_dir)
        return stack_info_dict
    
    def translate_stacks_to_envi(index_stacker, stack_info_dict):
        envi_dataset_path_dict = {}
        for vrt_file in sorted(stack_info_dict.keys()):
            stack_list = stack_info_dict[vrt_file]
            layer_name_list = ['Band_%d %s-%s %s' % (tile_index + 1, 
                                                     stack_list[tile_index]['satellite_tag'],
                                                     stack_list[tile_index]['sensor_name'],
                                                     stack_list[tile_index]['start_datetime'].isoformat()
                                                     ) for tile_index in range(len(stack_list))]
            
            envi_dataset_path = vrt2bin(vrt_file, output_dataset_path=None,
                    file_format='ENVI', file_extension='_envi', format_options=None,
                    layer_name_list=layer_name_list, 
                    no_data_value=stack_list[0]['nodata_value'], # Will all be the same
                    overwrite=index_stacker.refresh,
                    debug=index_stacker.debug)
            
            envi_dataset_path_dict[vrt_file] = envi_dataset_path
            
        logger.info('Finished translating %d temporal stack files to Envi in %s.', len(envi_dataset_path_dict), index_stacker.output_dir)
        return envi_dataset_path_dict
            
    def calc_stats(index_stacker, stack_info_dict, envi_dataset_path_dict):
        stats_dataset_path_dict = {}
        for vrt_file in sorted(stack_info_dict.keys()):
            envi_dataset_path = envi_dataset_path_dict[vrt_file]
            stack_list = stack_info_dict[vrt_file]
            
            if vrt_file.find('WATER') > -1: # Don't run stats on water analysis
                continue
            
            stats_dataset_path = envi_dataset_path.replace('_envi', '_stats_envi')
            stats_dataset_path_dict[vrt_file] = stats_dataset_path
            
            if os.path.exists(stats_dataset_path) and not index_stacker.refresh:
                logger.info('Skipping existing stats file %s', stats_dataset_path)
                continue
            
            logger.info('Calculating temporal summary stats for %s', envi_dataset_path)
            #TODO: fix temporal_stats_numexpr_module so it still edits hdr file properly
            temporal_stats_numexpr_module.main(envi_dataset_path, stats_dataset_path, 
                                               noData=stack_list[0]['nodata_value'],
                                               provenance=True # Create two extra bands for datetime and satellite provenance
                                               )
            
        logger.info('Finished calculating %d temporal summary stats files in %s.', len(stats_dataset_path_dict), index_stacker.output_dir)
        return stats_dataset_path_dict
        
    def update_stats_metadata(index_stacker, stack_info_dict, envi_dataset_path_dict, stats_dataset_path_dict):
        for vrt_file in sorted(stack_info_dict.keys()):
            stats_dataset_path = stats_dataset_path_dict.get(vrt_file)
            if not stats_dataset_path: # Don't proceed if no stats file (e.g. WATER)
                continue
            
            stack_list = stack_info_dict[vrt_file]
            envi_dataset_path = envi_dataset_path_dict[vrt_file]
            start_datetime = stack_list[0]['start_datetime']
            end_datetime = stack_list[-1]['end_datetime']
            description = 'Statistical summary for %s' % stack_list[0]['band_name']

            # Reopen output file and write source dataset to metadata
            stats_dataset = gdal.Open(stats_dataset_path, gdalconst.GA_Update)
            metadata = stats_dataset.GetMetadata()
            metadata['source_dataset'] = envi_dataset_path # Should already be set
            metadata['start_datetime'] = start_datetime.isoformat()
            metadata['end_datetime'] = end_datetime.isoformat()
            stats_dataset.SetMetadata(metadata)
            stats_dataset.SetDescription(description)
            stats_dataset.FlushCache()
            
        logger.info('Finished updating metadata in %d temporal summary stats files in %s.', len(stats_dataset_path_dict), index_stacker.output_dir)
            
        
                     
    # Main function starts here
    # Stacker class takes care of command line parameters
    index_stacker = IndexStacker()
    
    if index_stacker.debug:
        console_handler.setLevel(logging.DEBUG)
    
    # Check for required command line parameters
    assert index_stacker.x_index, 'Tile X-index not specified (-x or --x_index)'
    assert index_stacker.y_index, 'Tile Y-index not specified (-y or --y_index)'
    assert index_stacker.output_dir, 'Output directory not specified (-o or --output)'
    
    stack_info_dict = assemble_stack(index_stacker)
    envi_dataset_path_dict = translate_stacks_to_envi(index_stacker, stack_info_dict)
    stats_dataset_path_dict = calc_stats(index_stacker, stack_info_dict, envi_dataset_path_dict)
    update_stats_metadata(index_stacker, stack_info_dict, envi_dataset_path_dict, stats_dataset_path_dict)
    


