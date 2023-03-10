#!/usr/bin/env python
# coding: utf-8

# In[ ]:


# ! pip install pandas
# ! pip install requests
# ! pip install plotly
# ! pip install datetime
# ! pip install os
# ! pip freeze = requirements.txt


# In[ ]:


import pandas as pd
import requests as r
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import os
import time
import sys
sys.path.append('../helper_functions')
import subgraph_utils as subg
import defillama_utils as dfl
import pandas_utils as pu


# In[ ]:


pwd = os.getcwd()
# Verify that our path is right
if 'op_rewards_tracking' in pwd:
    prepend = ''
else:
    prepend = 'op_rewards_tracking/'
print(pwd)
# if TVL by token is not available, do we fallback on raw TVL (sensitive to token prices)?
do_fallback_on_raw_tvl = True
str_fallback_indicator = '' #Dont append any indicator yet, since it screws up joins


# In[ ]:


# Protocol Incentive Start Dates
# Eventually, move this to its own file / csv
protocols = pd.read_csv('inputs/' + 'op_incentive_protocols.csv')
#evaluate arrays as array
protocols['contracts'] = protocols['contracts'].apply(pu.str_to_list)
# display(protocols)

protocol_name_mapping = pd.DataFrame(
    [
        ['aave-v3','aave'],
        ['beefy','beefy finance'],
        ['revert-compoundor','revert finance'],
        ['cbridge','celer'],
        ['pickle','pickle finance'],
        ['stargate','stargate finance'],
        ['sushi-trident','sushi']
        
    ]
    ,columns=['slug','app_name']
)

date_cols = ['start_date', 'end_date']
for d in date_cols:
    protocols[d] = pd.to_datetime( protocols[d] )

protocols = protocols.merge(protocol_name_mapping,on='slug', how = 'left')

# For subgraphs
protocols['protocol'] = protocols['slug']
protocols['app_name'] = protocols['app_name'].combine_first(protocols['slug'])
protocols['id_format'] = protocols['slug'].str.replace('-',' ').str.title()
protocols['program_name'] = np.where( ( (protocols['name'] == '') )
                                    , protocols['id_format']
                                    , protocols['id_format'] + ' - ' + protocols['name']
                                    )
protocols['top_level_name'] = np.where( protocols['name'] == ''
                                    , protocols['id_format']
                                    , protocols['name']
                                    )
# protocols['program_name'] = np.where( protocols['name'] == '', protocols['id_format'], protocols['name'])

protocols = protocols.sort_values(by='start_date', ascending=True)
                    
# display(protocols)


# In[ ]:


# Pull Data
dfl_protocols = protocols[protocols['data_source'] == 'defillama'].copy()

#drop og protocol column to avoid collisions
dfl_protocols = dfl_protocols.drop('protocol', axis=1)

dfl_slugs = dfl_protocols[['slug']].drop_duplicates()
# display(dfl_slugs)
df_dfl = dfl.get_range(dfl_slugs[['slug']],['Optimism'], fallback_on_raw_tvl= do_fallback_on_raw_tvl)

df_dfl['is_raw_tvl'] = np.where(df_dfl['slug'].str.endswith('*'), 1, 0)


# In[ ]:


# Format Columns
# df_dfl['app_name'] = df_dfl['app_name'].combine_first(df_dfl['protocol'])

# df_dfl['id_format'] = df_dfl['slug'].str.replace('-',' ').str.title()

# df_dfl['app_name'] = df_dfl['app_name'].str.replace('-',' ').str.title()


df_dfl = df_dfl.merge(dfl_protocols, on ='slug')
# display(df_dfl)

# df_dfl['protocol'] = df_dfl['slug']#.combine_first(df_dfl['slug_y'])
# display(df_dfl)
df_dfl['name'] = df_dfl['name_y'].combine_first(df_dfl['name_x']) + \
                        np.where(df_dfl['protocol'].str.endswith('*'), '*','') #IF Raw TVL, pull this in
# display(df_dfl)
df_dfl['top_level_name'] = df_dfl['top_level_name'] + np.where(df_dfl['protocol'].str.endswith('*'), '*','') #IF Raw TVL, pull this in

df_dfl['program_name'] = df_dfl['program_name'] + np.where(df_dfl['protocol'].str.endswith('*'), '*','') #IF Raw TVL, pull this in

df_dfl = df_dfl[['date', 'token', 'token_value', 'usd_value', 'protocol', 'start_date','end_date','program_name','app_name','top_level_name']]

# display(df_dfl)


# In[ ]:


subg_protocols = protocols[protocols['data_source'].str.contains('pool-')].copy()
subg_protocols['og_app_name'] = subg_protocols['app_name']
subg_protocols['og_protocol'] = subg_protocols['slug']
subg_protocols['og_top_level_name'] = subg_protocols['top_level_name']
subg_protocols['df_source'] = subg_protocols['data_source'].str.split('-').str[-1]
# display(subg_protocols)


# In[ ]:


dfs_sub = []
for index, program in subg_protocols.iterrows():
        min_tsmp = int( pd.to_datetime(program['start_date']).timestamp() )
        min_tsmp = min_tsmp - 1000 #add some buffer
        source_slug = program['source_slug']
        df_source = program['df_source']
        for c in program['contracts']:
                # print(df_source + ' - ' +source_slug + ' - ' + c)
                # messari generalized
                if df_source == 'messari':
                        sdf = subg.get_messari_format_pool_tvl(source_slug, c.lower(), min_ts = min_tsmp)
                # subgraph specific
                elif df_source == 'curve':
                        sdf = subg.get_curve_pool_tvl(c.lower(), min_ts = min_tsmp)
                elif df_source == 'velodrome':
                        sdf = subg.get_velodrome_pool_tvl(c.lower(), min_ts = min_tsmp)
                elif df_source == 'hop':
                        sdf = subg.get_hop_pool_tvl(c, min_ts = min_tsmp)
                        
                sdf['start_date'] = program['start_date']
                sdf['end_date'] = program['end_date']
                sdf['program_name'] = program['program_name']
                sdf['protocol'] = program['og_protocol']
                sdf['app_name'] = program['og_app_name']
                sdf['top_level_name'] = program['og_top_level_name']

                sdf['token_value'] = sdf['token_value'].fillna(0)
                sdf['usd_value'] = sdf['usd_value'].fillna(0)
                dfs_sub.append(sdf)
df_df_sub = pd.concat(dfs_sub)
# display(df_df_sub[df_df_sub['program_name'].str.contains('Velo')])


# In[ ]:


# display(df_df_sub.sort_values(by='date'))
# display(df_dfl[df_dfl['protocol']=='defiedge'])


# In[ ]:


df_df_comb = pd.concat([df_dfl, df_df_sub])
#remove * from protocol
df_df_comb['protocol'] = df_df_comb['protocol'].str[:-1].where(df_df_comb['protocol'].str[-1] == '*', df_df_comb['protocol'])


# display(df_df_comb)
df_df_comb['start_date'] = pd.to_datetime(df_df_comb['start_date'])
df_df_comb['end_date'] = pd.to_datetime(df_df_comb['end_date'])
df_df_comb['date'] = pd.to_datetime(df_df_comb['date'])
# display(df_df_comb)

# Make sure datatypes are clean
df_df_comb['token_value'] = df_df_comb['token_value'].astype('float64')
df_df_comb['usd_value'] = df_df_comb['usd_value'].astype('float64')

#create an extra day to handle for tokens dropping to 0
#this is a temp fix - longer term also: Get max of a token x date and do date + 1 = 0 (i.e. weth to eth flips)
# find intermediate gaps. Call it a 0 flow in the in-between dates (i.e. pooltogether)
df_df_shift = df_df_comb.copy()
df_df_shift['date'] = df_df_shift['date'] + timedelta(days=1)
df_df_shift['token_value'] = 0
df_df_shift['usd_value'] = 0
#merge back in
df_df = pd.concat([df_df_comb,df_df_shift])
df_df = df_df[df_df['date'] <= pd.to_datetime("today") ]



# Group - Exclude End Date since this is often null and overwritting could be weird, especially if we actually know an end date
df_df['start_date'] = df_df['start_date'].fillna( pd.to_datetime("today").floor('d') )
#Generate End Date Column
df_df['end_date_30'] = df_df['end_date'].fillna(pd.to_datetime("today")).dt.floor('d') + timedelta(days = 30)

# display(
#         df_df[(df_df['protocol']=='velodrome')] 
#         )

df_df = df_df.groupby(['date','token','protocol','start_date','end_date_30','program_name','app_name','top_level_name']).sum().reset_index()

# display(df_df)
# display(
#         df_df[(df_df['protocol']=='pooltogether')] 
#         )


# In[ ]:


data_df = df_df.copy()#merge(cg_df, on=['date','token'],how='inner')

# data_df = data_df[data_df['token_value'] > 0] #Exclude this, so we can read flows

data_df.sort_values(by='date',inplace=True)
# data_df['token_value'] = data_df['token_value'].replace(0, np.nan) #keep zeroes
data_df['price_usd'] = data_df['usd_value']/data_df['token_value']

data_df['rank_desc'] = data_df.groupby(['protocol', 'program_name', 'token'])['date'].\
                            rank(method='dense',ascending=False).astype(int)

data_df.sort_values(by='date',inplace=True)

last_df = data_df[data_df['rank_desc'] == 1]
last_df = last_df.rename(columns={'price_usd':'last_price_usd'})
last_df = last_df[['token','protocol','program_name','last_price_usd']]
# display(last_df)


# In[ ]:


data_df = data_df.merge(last_df, on=['token','protocol','program_name'], how='left')

data_df['last_token_value'] = data_df.groupby(['token','protocol', 'program_name'])['token_value'].shift(1)

data_df['last_price_usd'] = data_df.groupby(['token','protocol', 'program_name'])['price_usd'].shift(1)

# If first instnace of token, make sure there's no price diff
data_df['last_price_usd'] = data_df[['last_price_usd', 'price_usd']].bfill(axis=1).iloc[:, 0]
#Forward fill if token drops off
data_df['price_usd'] = data_df[['price_usd','last_price_usd']].bfill(axis=1).iloc[:, 0]

data_df['last_token_value'] = data_df['last_token_value'].fillna(0)

data_df['net_token_flow'] = data_df['token_value'] - data_df['last_token_value']
data_df['net_price_change'] = data_df['price_usd'] - data_df['last_price_usd']

data_df['net_dollar_flow'] = data_df['net_token_flow'] * data_df['price_usd']
data_df['last_price_net_dollar_flow'] = data_df['net_token_flow'] * data_df['last_price_usd']

data_df['net_price_stock_change'] = data_df['last_token_value'] * data_df['net_price_change']


# display(data_df)


# In[ ]:


#filter before start date
data_df = data_df[data_df['date']>= data_df['start_date']]
# filter lte end date + 30
data_df = data_df[data_df['date']<= data_df['end_date_30']]
data_df.drop('end_date_30', axis=1, inplace=True)

if not os.path.exists(prepend + "csv_outputs"):
        os.mkdir(prepend + "csv_outputs")
data_df.to_csv(prepend + 'csv_outputs/' + 'tvl_flows_by_token.csv')


# In[ ]:


# data_df[data_df['protocol']=='perpetual-protocol'].sort_values(by='date')
# data_df.fillna(0)
# data_df.sample(5)
# data_df[(data_df['protocol'] == 'pooltogether') & (data_df['date'] >= '2022-10-06') & (data_df['date'] <= '2022-10-12')].tail(10)


# In[ ]:


netdf_df = data_df[['date','protocol','program_name','net_dollar_flow','net_price_stock_change','last_price_net_dollar_flow','usd_value','app_name','top_level_name']]

netdf_df = netdf_df.groupby(['date','protocol','program_name','app_name','top_level_name']).sum(['net_dollar_flow','net_price_stock_change','last_price_net_dollar_flow','usd_value'])

# reset & get program data
netdf_df.reset_index(inplace=True)

netdf_df['tvl_change'] = netdf_df['usd_value'] - netdf_df.groupby(['protocol', 'program_name','app_name'])['usd_value'].shift(1)
netdf_df['error'] = netdf_df['tvl_change'] - (netdf_df['net_dollar_flow'] + netdf_df['net_price_stock_change'])

cumul_cols = ['net_dollar_flow','last_price_net_dollar_flow','net_price_stock_change']
for c in cumul_cols:
        netdf_df['cumul_' + c] = netdf_df.groupby(['protocol', 'program_name'])[c].cumsum()
        # netdf_df['cumul_last_price_net_dollar_flow'] = netdf_df.groupby(['protocol', 'program_name'])['last_price_net_dollar_flow'].cumsum()
        # netdf_df['cumul_net_price_stock_change'] = netdf_df.groupby(['protocol', 'program_name'])['net_price_stock_change'].cumsum()


# print(protocols.columns)
# print(netdf_df.columns)

# Bring Program info Back In
join_cols = ['program_name','protocol','app_name','top_level_name']
join_cols_join = [col + '_join' for col in join_cols]
for c in join_cols:
        netdf_df[c+'_join'] = netdf_df[c].str[:-1].where(netdf_df[c].str[-1] == '*', netdf_df[c])
        protocols[c+'_join'] = protocols[c]

protocol_cols = ['include_in_summary','op_source','start_date','end_date','num_op'] + join_cols_join

netdf_df = netdf_df.merge(protocols[protocol_cols], on=join_cols_join)

# for c in join_cols_join:
#         old_col = c.replace("_join", "")
#         netdf_df[old_col] = netdf_df[c]

#For Summary
if_ended_cols = ['net_dollar_flow','last_price_net_dollar_flow']
new_ended_cols = []
for e in if_ended_cols:
        netdf_df['cumul_' + e + '_if_ended'] = netdf_df[~netdf_df['end_date'].isna()].groupby(['protocol', 'program_name'])[e].cumsum()
        new_ended_cols.append('cumul_' + e + '_if_ended')
#
# print(new_ended_cols)
# display(netdf_df[netdf_df['protocol'] == 'revert-compoundor'])

for d in date_cols:
        netdf_df[d] = pd.to_datetime(netdf_df[d])

# check info at program end
# display(program_end_df)
# display(netdf_df[netdf_df['protocol'] == 'velodrome'])


# In[ ]:


summary_cols = ['cumul_net_dollar_flow','cumul_last_price_net_dollar_flow','cumul_net_price_stock_change','num_op']

netdf_df['program_rank_desc'] = netdf_df.groupby(['protocol', 'program_name'])['date'].\
                            rank(method='dense',ascending=False).astype(int)

# for sc in summary_cols:
#         netdf_df[sc] = netdf_df[sc].astype('int64')
summary_cols = summary_cols + new_ended_cols
# print(summary_cols)
program_end_df = netdf_df[
        (pd.to_datetime(netdf_df['date']) == pd.to_datetime(netdf_df['end_date']) ) # is at end date
        | (netdf_df['program_rank_desc'] ==1)# or is latest date
                        ].groupby(['protocol', 'program_name','app_name']).sum(numeric_only=True)
program_end_df.reset_index(inplace=True)
# display(program_end_df)

# display(program_end_df)
for s in summary_cols:
        s_new = s+'_at_program_end'
        program_end_df = program_end_df.rename(columns={s:s_new})
        netdf_df = netdf_df.merge(program_end_df[['protocol','program_name',s_new]], on=['protocol','program_name'], how = 'left')

# netdf_df['cumul_net_dollar_flow_at_program_end'] = netdf_df[is_program_end].groupby(['protocol', 'program_name']).sum(['cumul_net_dollar_flow'])
# netdf_df['cumul_last_price_net_dollar_flow_at_program_end'] = netdf_df[netdf_df['date'] == netdf_df['end_date']]['last_price_net_dollar_flow'].groupby(['protocol', 'program_name']).cumsum()
# netdf_df['cumul_net_price_stock_change_at_program_end'] = netdf_df[netdf_df['date'] == netdf_df['end_date']]['net_price_stock_change'].groupby(['protocol', 'program_name']).cumsum()

# netdf_df.loc[ netdf_df['end_date'] == pd.to_datetime("2000-01-01"), 'end_date' ] == pd.to_datetime("1900-01-01")

# np.where( netdf_df['end_date'] <= pd.to_datetime("2000-01-01") , pd.NaT , netdf_df['end_date'] )
# display(netdf_df[netdf_df['protocol'] == 'hundred-finance'].sort_values(by='program_rank_desc'))


# In[ ]:


# netdf_df[(netdf_df['date'] >= '2022-10-06') & (netdf_df['date'] <= '2022-10-12')].tail(10)
# netdf_df.tail()


# In[ ]:


during_str = 'During Program'
post_str = 'Post-Program'

netdf_df['period'] = np.where(
        netdf_df['date'] > netdf_df['end_date'], post_str, during_str
        )
if not os.path.exists(prepend + "csv_outputs"):
        os.mkdir(prepend + "csv_outputs")
netdf_df.to_csv(prepend + 'csv_outputs/op_summer_daily_stats.csv', index=False)

#SORT FOR CHARTS
netdf_df = netdf_df.sort_values(by=['top_level_name','program_name','app_name'], ascending=[True,True,True])
# display(netdf_df.head())
# print(netdf_df.columns)


# In[ ]:


latest_data_df = netdf_df[netdf_df['program_rank_desc'] == 1]
latest_data_df['date'] = latest_data_df['date'].dt.date
# latest_data_df['days_since_program_end'] 
# latest_data_df.loc[latest_data_df['end_date'] != '', 'days_since_program_end'] = \
#         pd.to_datetime(latest_data_df['end_date']) \
#         - pd.to_datetime(latest_data_df['date'])

latest_data_df['days_since_program_end'] = \
        np.where(latest_data_df['end_date'] != '',
        pd.to_datetime(latest_data_df['end_date']) \
        - pd.to_datetime(latest_data_df['date']) \
        , \
        pd.to_datetime(latest_data_df['date']) \
        - pd.to_datetime(latest_data_df['start_date']) \
        )
latest_data_df = latest_data_df.sort_values(by='start_date', ascending=False)
# display(latest_data_df)


# In[ ]:


# Generate agg summary df
season_summary_pds = latest_data_df[latest_data_df['include_in_summary'] == 1].copy()

season_summary_s0_no_perp = season_summary_pds[(season_summary_pds['op_source'] == 'Gov Fund - Phase 0') \
                                                & (season_summary_pds['protocol'] != 'perpetual-protocol')]

season_summary_s0_no_perp['op_source'] = 'Gov Fund - Phase 0 (Excl. Perp)'

season_summary_raw = pd.concat([season_summary_pds, season_summary_s0_no_perp])

season_summary_completed_raw = season_summary_pds[season_summary_pds['end_date'] < pd.to_datetime("today")] #only ended summaries



# In[ ]:


# SEASON SUMMARY
season_summary = season_summary_raw.groupby('op_source').sum()
# display(season_summary.head())
season_summary.reset_index()
# create a row with total values
season_summary_total_raw = season_summary_raw.copy()
season_summary_total_raw['op_source'] = '- TOTAL -'
season_summary_total = pd.DataFrame(season_summary_total_raw.groupby('op_source').sum())

# concatenate the aggregated grouped data with the total row
season_summary = pd.concat([season_summary, season_summary_total])
season_summary.reset_index(inplace=True)
# season_summary.head()

# SEASON SUMMARY IF COMPLETED - loops were weird, so doing it this way

season_summary_completed = season_summary_completed_raw.groupby('op_source').sum()
# display(season_summary.head())
season_summary_completed.reset_index()
# create a row with total values
season_summary_completed_total_raw = season_summary_completed_raw.copy()
season_summary_completed_total_raw['op_source'] = '- TOTAL -'
season_summary_completed_total = pd.DataFrame(season_summary_completed_total_raw.groupby('op_source').sum())

# concatenate the aggregated grouped data with the total row
season_summary_completed = pd.concat([season_summary_completed, season_summary_completed_total])
season_summary_completed.reset_index(inplace=True)
# season_summary.head()


# In[ ]:


# print(latest_data_df.columns)
# print(season_summary.columns)


# In[ ]:


df_list = [latest_data_df, season_summary, season_summary_completed]
latest_data_df.name = 'op_summer_latest'
season_summary.name = 'season_summary'
season_summary_completed.name = 'season_summary_completed'

for df in df_list:
        # Fix 0 columns
        for col in df.columns:
                if "_at_program_end" in col:
                        df[col] = df[col].astype(float)
                        df[col] = np.where(df[col] == 0, np.NaN, df[col])

        df['cumul_flows_per_op_at_program_end'] = df['cumul_net_dollar_flow_at_program_end'] / df['num_op_at_program_end']
        
        df['cumul_flows_per_op_latest'] = df['cumul_net_dollar_flow'] / df['num_op']

        df['last_price_net_dollar_flows_per_op_at_program_end'] = df['cumul_last_price_net_dollar_flow_at_program_end'] / df['num_op_at_program_end']
        df['last_price_net_dollar_flows_per_op_latest'] = df['cumul_last_price_net_dollar_flow'] / df['num_op']

        df['flows_retention'] = \
                        df['cumul_net_dollar_flow_if_ended'] / df['cumul_net_dollar_flow_at_program_end'] \
                        * np.where(df['cumul_net_dollar_flow'] < 0, -1, 1)
        df['last_price_net_dollar_flows_retention'] = \
                        df['cumul_last_price_net_dollar_flow_if_ended'] / df['cumul_last_price_net_dollar_flow_at_program_end'] \
                        * np.where(df['cumul_last_price_net_dollar_flow'] < 0, -1, 1)


# In[ ]:


for df in df_list:
    # display(df)
    #get df name
    col_list = [
        'date','include_in_summary','program_name','app_name','num_op','period','op_source','start_date','end_date'
        ,'cumul_net_dollar_flow_at_program_end'
        ,'cumul_net_dollar_flow'
        ,'cumul_flows_per_op_at_program_end','cumul_last_price_net_dollar_flow_at_program_end'
        ,'cumul_flows_per_op_latest', 'cumul_last_price_net_dollar_flow'
        , 'last_price_net_dollar_flows_per_op_at_program_end','last_price_net_dollar_flows_per_op_latest'
        ,'flows_retention', 'last_price_net_dollar_flows_retention'
    ]
    summary_exclude_list = ['date','program_name','app_name','period','start_date','end_date']
    sort_cols = ['Start','# OP']

    if df.name == 'op_summer_latest':
        html_name = df.name + '_stats'
        sort_order = [False, False]
    elif 'season_summary' in df.name:
        html_name = df.name + '_stats'
        sort_cols = ['Source','# OP']
        sort_order = [False, True] # so totals goes to bottom
        col_list = [x for x in col_list if x not in summary_exclude_list]
    else:
        html_name = 'other'

    df_format = df.copy()
    new_cols = df_format.columns
    drop_cols = ['net_dollar_flow',
        'net_price_stock_change', 'last_price_net_dollar_flow', 'usd_value',
        'tvl_change', 'error'
        ]
    new_cols = new_cols.drop(drop_cols)
    # print(new_cols)
    df_format = df_format[new_cols]

    # df_format['num_op'] = df_format['num_op'].apply(lambda x: '{0:,.0f}'.format(x) if not pd.isna(x) else x )
    # df_format['flows_retention'] = df_format['flows_retention'].apply(lambda x: '{:,.1%}'.format(x) if not pd.isna(x) else x )
    # df_format['last_price_net_dollar_flows_retention'] = df_format['last_price_net_dollar_flows_retention'].apply(lambda x: '{:,.1%}'.format(x) if not pd.isna(x) else x )

    df_format = df_format[col_list]
    df_format = df_format.reset_index(drop=True)

    if not os.path.exists(prepend + "csv_outputs"):
        os.mkdir(prepend + "csv_outputs")
    if not os.path.exists(prepend + "img_outputs"):
        os.mkdir(prepend + "img_outputs")
        os.mkdir(prepend + "img_outputs/overall")
        os.mkdir(prepend + "img_outputs/overall/png")
        os.mkdir(prepend + "img_outputs/overall/svg")
        os.mkdir(prepend + "img_outputs/overall/html")
    df_format.to_csv(prepend + 'csv_outputs/' + html_name + '.csv', index=False)

    format_cols = [
        'cumul_flows_per_op_at_program_end','cumul_flows_per_op_latest','last_price_net_dollar_flows_per_op_at_program_end','last_price_net_dollar_flows_per_op_latest']
    format_mil_cols = [
        'cumul_net_dollar_flow', 'cumul_last_price_net_dollar_flow',
        'cumul_net_dollar_flow_at_program_end',
        'cumul_last_price_net_dollar_flow_at_program_end'
    ]
    # for f in format_cols:
        # df_format[f] = df_format[f].apply(lambda x: '${0:,.2f}'.format(x) if not pd.isna(x) else x )
        # df_format[f] = df_format[f].apply(lambda x: round(x,1) if not pd.isna(x) else x )
    # for fm in format_mil_cols:
    #     df_format[fm] = df_format[fm].apply(lambda x: '${0:,.2f}M'.format(x/1e6) if not pd.isna(x) else x )


    df_format = df_format.rename(columns={
        'date':'Date', 'program_name':'Program', 'num_op': '# OP'
        ,'period': 'Period','op_source': 'Source','start_date':'Start','end_date':'End'
        ,'cumul_net_dollar_flow_at_program_end':'Net Flows (at End Date)'
        ,'cumul_net_dollar_flow':'Net Flows (End + 30)'
        ,'cumul_flows_per_op_at_program_end': 'Net Flows per OP (at End Date)'
        ,'cumul_flows_per_op_latest': 'Net Flows per OP (End + 30)'
        ##
        ,'cumul_last_price_net_dollar_flow_at_program_end':'Net Flows @ Current Prices (at End Date)'
        ,'cumul_last_price_net_dollar_flow':'Net Flows @ Current Prices (End + 30)'
        ,'last_price_net_dollar_flows_per_op_at_program_end': 'Net Flows per OP @ Current Prices (at End Date)'
        ,'last_price_net_dollar_flows_per_op_latest': 'Net Flows per OP @ Current Prices (End + 30)'
        ,'flows_retention' : 'Net Flows Retained'
        ,'last_price_net_dollar_flows_retention' : 'Net Flows Retained @ Current Prices'
    })

    df_col_list = list(df_format.columns)
    df_col_list.remove('include_in_summary')

    format_mil_cols_clean = [x for x in df_col_list
                             if ('Flows' in x) & ('Retained' not in x)]
    # print(format_mil_cols_clean)
    format_pct_cols_clean = [x for x in df_col_list
                             if 'Retained' in x]

    format_op_cols_clean = ['# OP']
    # [
    #     '# OP','Net Flows (at End Date)',
    #     'Net Flows (End + 30)', 'Net Flows @ Current Prices (End + 30)',
    #     'Net Flows @ Current Prices (at End Date)',
    #     'Net Flows @ Current Prices (at End Date)'
    # ]
    df_format = df_format.fillna('')
    df_format = df_format.reset_index(drop=True)
    df_format = df_format.sort_values(by=sort_cols, ascending = sort_order)

    # df_format.to_html(
    #     prepend + "img_outputs/app/" + html_name + ".html",
    #     classes='table table-stripped')
    # display(df_format[format_mil_cols_clean])
    # fig_tbl = px.table(df_format[df_col_list], sortable=True)
    # fig_tbl.show()
    
    #chatgpt goat?
    header = dict(values=df_col_list, fill_color='darkgray', align='center')#, sort_action='native')

    # format the numbers in mil_columns and store the result in a list of lists
    values = [[pu.format_num(x,'$') if col in format_mil_cols_clean else 
           pu.format_num(x) if col in format_op_cols_clean else 
           pu.format_pct(x) if col in format_pct_cols_clean else x 
           for x in df_format[col]] for col in df_col_list]

    cells = dict(values=values, fill_color=['white', 'lightgray'] * (len(df_format)//2+1), align='right')#, line_break=True)

    data = [go.Table(header=header, cells=cells)]

    layout = go.Layout(title='TVL & Flows Stats')#, width='100%')

    fig_tbl = go.Figure(data=data, layout=layout)
    # fig_tbl.show()
    # pd_html = pu.generate_html(df_format[df_col_list])
    # pd_html = pu.DataTable(df_format[df_col_list]).data

    # print(type(pd_html))
    # open(prepend + "img_outputs/app/html/" + html_name + ".html", "w").write(pd_html)

    if not os.path.exists(prepend+'img_outputs/app'):
        os.mkdir(prepend+'img_outputs/app')
        os.mkdir(prepend+'img_outputs/app/png')
        os.mkdir(prepend+'img_outputs/app/svg')
        os.mkdir(prepend+'img_outputs/app/html')

    fig_tbl.write_html(prepend+'img_outputs/app/html/'+html_name+'.html', include_plotlyjs='cdn')


# In[ ]:


#Filter for Charts

netdf_df = netdf_df[netdf_df['date'] <= pd.to_datetime("today").floor('d')]


# In[ ]:


fig = px.line(netdf_df, x="date", y="net_dollar_flow", color="program_name", \
             title="Daily Liquidity Flows Since Program Announcement",\
            labels={
                     "date": "Day",
                     "net_dollar_flow": "Net Liquidity Flows (USD)"
                 }
            )
fig.update_layout(
    legend_title="App Name"
)
fig.update_layout(yaxis_tickprefix = '$')
fig.write_image(prepend + "img_outputs/overall/svg/daily_ndf.svg")
fig.write_image(prepend + "img_outputs/overall/png/daily_ndf.png")
fig.write_html(prepend + "img_outputs/overall/daily_ndf.html", include_plotlyjs='cdn')



cumul_fig = go.Figure()
proto_names = netdf_df['program_name'].drop_duplicates()
# print(proto_names)
for p in proto_names:
    cumul_fig.add_trace(go.Scatter(x=netdf_df[netdf_df['program_name'] == p]['date'] \
                                   , y=netdf_df[netdf_df['program_name'] == p]['cumul_net_dollar_flow'] \
                                    ,name = p\
                                  ,fill='tozeroy')) # fill down to xaxis

cumul_fig.update_layout(yaxis_tickprefix = '$')
cumul_fig.update_layout(
    title="Cumulative Net Liquidity Flows Since Program Announcement<br><sup>For Ended Programs, we show continue to show flows through 30 days after program end. | * Shows raw TVL change, rather than flows</sup>",
    xaxis_title="Day",
    yaxis_title="Cumulative Net Liquidity Flows (USD)",
    legend_title="App Name",
#     color_discrete_map=px.colors.qualitative.G10
)
cumul_fig.write_image(prepend + "img_outputs/overall/svg/cumul_ndf.svg") #prepend + 
cumul_fig.write_image(prepend + "img_outputs/overall/png/cumul_ndf.png") #prepend + 
cumul_fig.write_html(prepend + "img_outputs/overall/cumul_ndf.html", include_plotlyjs='cdn')


fig_last = go.Figure()
proto_names = netdf_df['program_name'].drop_duplicates()
# print(proto_names)
for p in proto_names:
    fig_last.add_trace(go.Scatter(x=netdf_df[netdf_df['program_name'] == p]['date'] \
                                   , y=netdf_df[netdf_df['program_name'] == p]['cumul_last_price_net_dollar_flow'] \
                                    ,name = p\
                                  ,fill='tozeroy')) # fill down to xaxis

fig_last.update_layout(yaxis_tickprefix = '$')
fig_last.update_layout(
    title="Cumulative Net Flows since Program Announcement (At Most Recent Token Price)<br><sup>For Ended Programs, we show continue to show flows through 30 days after program end. | * Shows raw TVL change, rather than flows</sup>",
    xaxis_title="Day",
    yaxis_title="Cumulative Net Flows (USD) - At Most Recent Price",
    legend_title="App Name",
#     color_discrete_map=px.colors.qualitative.G10
)
fig_last.write_image(prepend + "img_outputs/overall/svg/cumul_ndf_last_price.svg")
fig_last.write_image(prepend + "img_outputs/overall/png/cumul_ndf_last_price.png")
fig_last.write_html(prepend + "img_outputs/overall/cumul_ndf_last_price.html", include_plotlyjs='cdn')
# cumul_fig.show()


# In[ ]:


# Program-Specific Charts

value_list = ['cumul_net_dollar_flow','cumul_last_price_net_dollar_flow']

for val in value_list:
  if val == 'cumul_last_price_net_dollar_flow':
    postpend = " - At Last Price"
    folder_path = "/last_price"
  else:
    postpend = ""
    folder_path = ""
  proto_names = netdf_df['program_name'].drop_duplicates()
  # print(proto_names)
  for p in proto_names:
      cumul_fig_app = go.Figure()
      p_df = netdf_df[netdf_df['program_name'] == p]
      # cumul_fig_app = px.area(p_df, x="date", y="cumul_net_dollar_flow", color="period")
      
      during_df = p_df[p_df['period'] == during_str]
      cumul_fig_app.add_trace(go.Scatter(x= during_df['date'] \
                                    , y= during_df[val] \
                                      , name = during_str \
                                    ,fill='tozeroy')) # fill down to xaxis
      
      post_df = p_df[p_df['period'] == post_str]
      cumul_fig_app.add_trace(go.Scatter(x= post_df['date'] \
                                    , y= post_df[val] \
                                      , name = post_str \
                                    ,fill='tozeroy')) # fill down to xaxis

      cumul_fig_app.update_layout(yaxis_tickprefix = '$')
      cumul_fig_app.update_layout(
          title=p + "<br><sup>Cumulative Net Flows since Program Announcement, Until Program End + 30 Days" + postpend + "</sup>",
          xaxis_title="Day",
          yaxis_title="Cumulative Net Flows (USD)",
          legend_title="Period",
      #     color_discrete_map=px.colors.qualitative.G10
      )
      
      if not os.path.exists(prepend + "img_outputs/app" + folder_path):
        os.mkdir(prepend + "img_outputs/app" + folder_path)
      if not os.path.exists(prepend + "img_outputs/app" + folder_path + "/svg"):
        os.mkdir(prepend + "img_outputs/app" + folder_path + "/svg")
      if not os.path.exists(prepend + "img_outputs/app" + folder_path + "/png"):
        os.mkdir(prepend + "img_outputs/app/" + folder_path + "/png")
      
      p_file = p
      p_file = p_file.replace(' ','_')
      p_file = p_file.replace(':','')
      p_file = p_file.replace('/','-')
      cumul_fig_app.write_image(prepend + "img_outputs/app" + folder_path + "/svg/cumul_ndf_" + p_file + ".svg") #prepend + 
      cumul_fig_app.write_image(prepend + "img_outputs/app" + folder_path + "/png/cumul_ndf_" + p_file + ".png") #prepend + 
      cumul_fig_app.write_html(prepend + "img_outputs/app" + folder_path + "/cumul_ndf_" + p_file + ".html", include_plotlyjs='cdn')
      # cumul_fig_app.show()


# In[ ]:


fig_last.show()
print("yay")


# In[ ]:


# ! jupyter nbconvert --to python optimism_incentives_app_net_flows.ipynb

