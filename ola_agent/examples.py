"""Explicit scripted examples: offline demos are NOT LLM predictions."""
EXAMPLES={
    'Extract the Pokemon demo API and export CSV.': {'route':'etl','actions':[
        {'action':'extract','source':'pokemon'}, {'action':'export'}, {'action':'finish'}]},
    'What payment methods are available?': {'route':'sql','sql':'SELECT DISTINCT payment_method FROM payments ORDER BY payment_method'},
    'Show collected revenue by city.': {'route':'sql','sql':"SELECT r.city, ROUND(SUM(p.amount_inr), 2) AS collected_revenue_inr FROM rides r JOIN payments p ON r.ride_id = p.ride_id WHERE r.status = 'Completed' AND p.payment_status = 'Captured' GROUP BY r.city ORDER BY collected_revenue_inr DESC"},
    'What is the cancellation rate by city?': {'route':'sql','sql':"SELECT city, COUNT(*) AS total_rides, ROUND(100.0 * SUM(CASE WHEN status != 'Completed' THEN 1 ELSE 0 END) / COUNT(*), 2) AS cancellation_pct FROM rides GROUP BY city ORDER BY cancellation_pct DESC"},
    'Who are the top 5 riders by collected revenue?': {'route':'sql','sql':"SELECT r.user_id, ROUND(SUM(p.amount_inr), 2) AS collected_revenue_inr FROM rides r JOIN payments p ON r.ride_id = p.ride_id WHERE p.payment_status = 'Captured' AND r.status = 'Completed' GROUP BY r.user_id ORDER BY collected_revenue_inr DESC, r.user_id LIMIT 5"},
    'Show average rating by vehicle type.': {'route':'sql','sql':'SELECT v.vehicle_type, ROUND(AVG(ra.rating), 2) AS average_rating, COUNT(*) AS rated_rides FROM rides r JOIN vehicles v ON r.vehicle_id = v.vehicle_id JOIN ratings ra ON r.ride_id = ra.ride_id GROUP BY v.vehicle_type ORDER BY average_rating DESC, v.vehicle_type'},
    'How many rides have no payment record?': {'route':'sql','sql':'SELECT COUNT(*) AS rides_without_payment FROM rides r LEFT JOIN payments p ON r.ride_id = p.ride_id WHERE p.payment_id IS NULL'},
    'Export completed rides as CSV.': {'route':'etl','actions':[
        {'action':'inspect'}, {'action':'filter','filters':[{'column':'status','operator':'eq','value':'Completed'}]},
        {'action':'export','format':'csv'}, {'action':'finish'}]},
    'Export completed rides longer than 20 km as JSON.': {'route':'etl','actions':[
        {'action':'inspect'}, {'action':'filter','filters':[{'column':'status','operator':'eq','value':'Completed'},{'column':'distance_km','operator':'gt','value':20}]},
        {'action':'export','format':'json'}, {'action':'finish'}]},
    'Count completed rides by city and export CSV.': {'route':'etl','actions':[
        {'action':'filter','filters':[{'column':'status','operator':'eq','value':'Completed'}]},
        {'action':'aggregate','group_by':['city'],'aggregation':'count'}, {'action':'export'}, {'action':'finish'}]},
}
