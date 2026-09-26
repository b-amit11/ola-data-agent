-- Only original synthetic fixtures. These local demo passwords are public by design.
CREATE TABLE users (user_id INTEGER PRIMARY KEY, city TEXT, signup_date DATE);
CREATE TABLE vehicles (vehicle_id INTEGER PRIMARY KEY, vehicle_type TEXT, driver_id INTEGER);
CREATE TABLE rides (ride_id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users,
    vehicle_id INTEGER REFERENCES vehicles, ride_date DATE, city TEXT, status TEXT,
    distance_km NUMERIC(10,2), fare_inr NUMERIC(10,2));
CREATE TABLE payments (payment_id INTEGER PRIMARY KEY, ride_id INTEGER REFERENCES rides,
    payment_method TEXT, payment_status TEXT, amount_inr NUMERIC(10,2));
CREATE TABLE ratings (rating_id INTEGER PRIMARY KEY, ride_id INTEGER REFERENCES rides, rating INTEGER);
COPY users FROM '/seed/users.csv' CSV HEADER;
COPY vehicles FROM '/seed/vehicles.csv' CSV HEADER;
COPY rides FROM '/seed/rides.csv' CSV HEADER;
COPY payments FROM '/seed/payments.csv' CSV HEADER;
COPY ratings FROM '/seed/ratings.csv' CSV HEADER;
CREATE INDEX ON payments(ride_id);
CREATE INDEX ON rides(ride_date);
CREATE ROLE demo_reader LOGIN PASSWORD 'demo_reader_local';
GRANT CONNECT ON DATABASE ola_demo TO demo_reader;
GRANT USAGE ON SCHEMA public TO demo_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO demo_reader;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER ROLE demo_reader SET default_transaction_read_only = on;
ALTER ROLE demo_reader SET statement_timeout = '3s';
