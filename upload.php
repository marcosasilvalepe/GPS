<?php 

	include 'dbh.inc.php';

	try {

		$response = array();
		$response['success'] = False;

		$input = json_decode(file_get_contents('php://input'));
		$data = (array) $input;

		$identifier = $data['identifier'];
		$identifier = sanitize($identifier);

		if ($identifier !== "unique_identifier") return;

		$epoch = 946684800; //FOR MICROPYTHON TIMESTAMP

		$imei = $data["imei"];
		$imei = sanitize($imei);

		foreach ($data["coordinates"] as $coordinates) {

			$coordinates = (array) $coordinates;

			$counter = $coordinates["counter"];
			$counter = sanitize($counter);

			$trip = $coordinates["trip"];
			$trip = sanitize($trip);

			if ($trip == 1) {
				$last_trip = select_query("SELECT trip FROM coordinates WHERE imei=$imei ORDER BY id DESC LIMIT 1;");
				if (count($last_trip) === 0) $trip = 1;
				else $trip = $last_trip[0]['trip'] + 1;
			}

			$latitude = $coordinates["latitude"];
			$latitude = sanitize($latitude);

			$longitude = $coordinates["longitude"];
			$longitude = sanitize($longitude);

			$engine_status = $coordinates["engine_status"];
			$engine_status = sanitize($engine_status);
			$engine_status = ($engine_status) ? 1 : 0; 

			$last_location = $coordinates["last_location"];
			if ($last_location) {

				$last_record = select_query("SELECT timestamp, speed, gprs, satellites FROM coordinates WHERE imei=$imei ORDER BY id DESC LIMIT 1;");
				if (count($last_record) === 0) return;

				$timestamp = $last_record[0]['timestamp'];
				$speed = $last_record[0]['speed'];
				$gprs = $last_record[0]['gprs'];
				$satellites = $last_record[0]['satellites'];

			} else {
				$timestamp = $coordinates["timestamp"];
				$timestamp = sanitize($timestamp);
				$timestamp = $timestamp + $epoch;

				$speed = $coordinates["speed"];
				$speed = sanitize($speed);

				$gprs = $coordinates["gprs"];
				$gprs = sanitize($gprs);

				$satellites = $coordinates["satellites"];
				$satellites = sanitize($satellites);	
			}

			$datetime = time();
			$now = date("Y-m-d H:i:s", $datetime);

			mysqli_query($conn, "
				INSERT INTO 
				coordinates (imei, date, timestamp, trip, counter, latitude, longitude, speed, satellites, gprs, engine_status) 
				VALUES (
					'$imei', 
					'$now',
					$timestamp,
					$trip,
					$counter,
					'$latitude', 
					'$longitude', 
					$speed, 
					$satellites,
					$gprs,
					$engine_status
				);
			");
		}

		//GET USER PREFERENCES
		$preferences = select_query("SELECT domain, max_saved_coordinates, store_coordinates, script_version, mcu_sleep, reboot FROM users WHERE imei='$imei';")[0];
		$response['trip'] = intval($trip);
		$response["domain"] = $preferences["domain"];
		$response['max_saved_coordinates'] = $preferences['max_saved_coordinates'];
		$response["store_coordinates"] = $preferences['store_coordinates'];
		$response["script_version"] = $preferences['script_version'];
		$response["mcu_sleep"] = intval($preferences['mcu_sleep']);
		$response["reboot"] = $preferences['reboot'];

		if ($response["reboot"] === 1) mysqli_query($conn, "UPDATE users SET reboot=0 WHERE imei=$imei;");

		http_response_code(200);
		$response['success'] = True;

	}
	catch(Exception $e) { $response['error'] = strval($e); }
	finally { echo json_encode($response); }
?>
