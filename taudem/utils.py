import os
import numpy as _np
import osgeo.gdal as _gd
import shutil

_NUMPY_TO_GDAL_TYPES={
    _np.dtype('f'):_gd.GDT_Float32,
    _np.dtype('d'):_gd.GDT_Float64,
    _np.dtype('int16'):_gd.GDT_Int16,
    _np.dtype('int32'):_gd.GDT_Int32
}

class MetadataArray(_np.ndarray):

    def __new__(cls, input_array, **kwargs):
        # Input array is an already formed ndarray instance
        # We first cast to be our class type
        obj = _np.asarray(input_array).view(cls)
        # add the new attribute to the created instance
        obj.metadata = kwargs
        # Finally, we must return the newly created object:
        return obj

    def __array_finalize__(self, obj):
        # see InfoArray.__array_finalize__ for comments
        if obj is None: return
        self.metadata = getattr(obj, 'metadata', None)

def to_geotiff(arr,gt,fn):
    driver = _gd.GetDriverByName('GTiff')
    outRaster = driver.Create(fn, arr.shape[1], arr.shape[0], 1, _NUMPY_TO_GDAL_TYPES[arr.dtype])
    if gt is not None:
        if hasattr(gt,'to_gdal'):
            gt = gt.to_gdal()
        outRaster.SetGeoTransform(gt)
    outband = outRaster.GetRasterBand(1)
    if hasattr(arr,'metadata'):
        outband.SetNoDataValue(arr.metadata.get('no_data_value',None))
    outband.WriteArray(arr)
#           outRasterSRS = osr.SpatialReference()
#           outRasterSRS.ImportFromEPSG(4326)
#           outRaster.SetProjection(outRasterSRS.ExportToWkt())
    outband.FlushCache()

def to_point_shp(points,fn):
    if hasattr(points,'to_file'):
        points.to_file(fn)
        return

    raise Exception('Unable to write shapefile. Unknown data representation.')

def clip(raster,polygons,all_touched=True):
    import rasterio as rio
    geom_bounds = tuple(polygons.bounds)

    fsrc = raster.read(bounds=geom_bounds)

    coverage_rst = rasterize_geom(geom,like=fsrc,all_touched=all_touched)

    masked = np.ma.MaskedArray(fsrc.arry,mask=np.logical_or(fsrc.array==fsrc.nodata,np.logical_not(coverage_rst)))

    return masked

def to_polygons(raster,shp_fn=None,transform=None):
    from osgeo import ogr
    tmp=None
    if not shp_fn or not isinstance(raster,str):
        import tempfile
        tmp = tempfile.mkdtemp(prefix='taudem_')

    if not isinstance(raster,str):
        tmp_fn = os.path.join(tmp,'raster.tif')
        to_geotiff(raster,transform,tmp_fn)
        raster = tmp_fn

    if not shp_fn:
        shp_fn = os.path.join(tmp,'polygons.shp')

    try:
        if os.path.exists(shp_fn):
            os.remove(shp_fn)
        drv = ogr.GetDriverByName("ESRI Shapefile")
        dst_ds = drv.CreateDataSource( shp_fn )
        dst_layer = dst_ds.CreateLayer(os.path.basename(shp_fn)[:-4], srs = None )
        newField = ogr.FieldDefn('GRIDCODE', ogr.OFTInteger)
        dst_layer.CreateField(newField)

        coverage = _gd.Open(raster)
        band = coverage.GetRasterBand(1)
        result = _gd.Polygonize( band, band.GetMaskBand(), dst_layer, 0, [], callback=None )
        dst_ds.SyncToDisk()

        if tmp:
            import geopandas as gpd
            return gpd.read_file(shp_fn)
    finally:
        if tmp:shutil.rmtree(tmp)

# from http://stackoverflow.com/a/377028
def which(program):
    import os
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None