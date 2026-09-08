"""夏季新風冷卻除濕及中性送風；依明確工況計算，房間不重複計新風。"""
from .core import moist_air_state, calculate_pau, apply_safety_factor, InputError

SOURCE='https://psychrometrics.github.io/psychrolib/_modules/psychrolib.html#GetHumRatioFromTWetBulb'

def wet_bulb(db,rh,pressure=101325):
    target=moist_air_state(db,rh,pressure)['humidity_ratio_kgkg'];lo,hi=0.,db
    for _ in range(60):
        mid=(lo+hi)/2
        try:w=from_db_wb(db,mid,pressure)['humidity_ratio_kgkg']
        except InputError:w=-1
        if w>target:hi=mid
        else:lo=mid
    return (lo+hi)/2

def from_db_wb(db, wb, pressure):
    if not 0 <= wb <= db <= 50: raise InputError('只支援0至50°C且WB≤DB')
    saturated=moist_air_state(wb,1,pressure)['humidity_ratio_kgkg']
    # ASHRAE SI wet-bulb relation as documented by PsychroLib, above freezing.
    w=((2501-2.326*wb)*saturated-1.006*(db-wb))/(2501+1.86*db-4.186*wb)
    pv=pressure*w/(0.621945+w)
    sat=moist_air_state(db,1,pressure)['humidity_ratio_kgkg']
    pvs=pressure*sat/(0.621945+sat)
    return moist_air_state(db,pv/pvs,pressure)

def neutral_fresh_air(airflow_ls, db=34, wb=28, supply_db=23, supply_rh=.55, pressure=101325, coil_rh=.95):
    inlet=from_db_wb(db,wb,pressure)
    supply=moist_air_state(supply_db,supply_rh,pressure)
    lo,hi=0.,supply_db
    for _ in range(70):
        mid=(lo+hi)/2
        if moist_air_state(mid,coil_rh,pressure)['humidity_ratio_kgkg']>supply['humidity_ratio_kgkg']:hi=mid
        else:lo=mid
    coil=moist_air_state((lo+hi)/2,coil_rh,pressure)
    raw=calculate_pau(inlet,coil,airflow_ls)
    mass=airflow_ls/1000/inlet['specific_volume_m3kg_da']
    reheat=mass*(supply['enthalpy_kjkg']-coil['enthalpy_kjkg'])
    net=mass*(inlet['enthalpy_kjkg']-supply['enthalpy_kjkg'])
    return {'inlet':inlet,'coil_outlet':coil,'supply':supply,'airflow_ls':airflow_ls,
        'airflow_reference':'入口實際體積流量','dry_air_mass_kg_s':mass,
        'raw_coil':raw,'sizing_coil':apply_safety_factor(raw),'reheat_kw':reheat,
        'net_outdoor_to_supply_kw':net,'source':SOURCE,
        'strategy':'新風冷卻除濕後再熱至23°C/55%RH；室內末端承擔原房間負荷，不另計新風負荷。',
        'assumptions':['氣壓101325Pa','盤管離風95%RH為設計目標，待原廠盤管選型驗證','再熱優先採可用冷凝熱回收，未據此扣減用電','盤管需求未包含實際風機熱及管道得熱，須按選定設備核對'],
        'conditions_status':'暫定設計工況'}
