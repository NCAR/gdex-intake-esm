"""
Testing the create catalog process

package version needed to be pined
intake-esm                2025.7.9
ecgtools                  Riley's fork version
pydantic                  2.11.9
"""

import ecgtools



def simple_parser(file_path, var_name=None):

    # create basic catalog item
    catalog_item = {'path':file_path, 'variable':var_name, 'format':'reference'}

    return catalog_item

b = ecgtools.Builder(
        paths=['/glade/u/home/chiaweih/gdex-arco-kerchunk/test_json/'],
        depth=0,
        exclude_patterns=None
    )

b.build(parsing_func=simple_parser, parsing_func_kwargs={'var_name': 'icec-sfc-fc-gauss'})


b.save(
        name='jra3q_test_catalog',
        path_column_name='path',
        variable_column_name='variable',
        format_column_name='format',
        data_format='reference',
        groupby_attrs=[
            'variable'
        ],
        aggregations=[
            {'type': 'union', 'attribute_name': 'variable'},
            {
                'type': 'join_existing',
                'attribute_name': 'time_range',
                'options': {'dim': 'time', 'coords': 'minimal', 'compat': 'override'},
            },
        ],
        catalog_type='file',
        description='JRA3Q test catalog',
        directory='./',
    )
