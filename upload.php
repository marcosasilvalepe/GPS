<?php  

	/* Prevent XSS input */
	$_GET   = filter_input_array(INPUT_GET, FILTER_SANITIZE_STRING);
	$_POST  = filter_input_array(INPUT_POST, FILTER_SANITIZE_STRING);

	$_REQUEST = (array)$_POST + (array)$_GET + (array)$_REQUEST;
	$dbServername = "localhost";
	$dbUsername = "dbuser";
	$dbPassword = "dbpassword";
	$dbName = "gps";
	$conn = mysqli_connect($dbServername, $dbUsername, $dbPassword, $dbName);
	$acentos = $conn -> query("SET NAMES 'utf8'");

	function sanitize($input) {
		global $conn;
		$input = trim($input);
		$input = stripslashes($input);
		$input = mysqli_real_escape_string($conn, $input);
		$input = htmlspecialchars($input);
		return $input;
	}

	function select_query($query) {
		global $conn;
		$result = $conn -> query($query);
		if ($result !== FALSE) $result = $result -> fetch_all(MYSQLI_ASSOC);
		$conn -> close();
		return $result;
	}

	$q = file_get_contents('php://input');
	$json_object = json_decode($q);
	$post_array = get_object_vars($json_object);

	//FILTER VARIABLE TO AVOID ANY1 POSTING DATA TO THE SCRIPT
	if ($post_array['?QSN2v3R+#']) {

		$epoch = 946684800; //FOR MICROPYTHON TIMESTAMP
		$version = sanitize($post_array['v']);
		$imei = sanitize($post_array['imei']);

		if ($post_array['array']) { $data_type="array"; } 
		else { $data_type="single"; }

		$data_array = $post_array['data'];

		foreach ($data_array as $key => $value) {

			$data = get_object_vars($value);

			$gps_counter = sanitize($data['counter']);
			$datetime = time();
			$now = date("Y-m-d H:i:s", $datetime);

			$timestamp = $data['ts'];
			if ($timestamp == "0") $timestamp = strtotime($now);
			else {
				$timestamp = sanitize($timestamp);
				$timestamp = intval($timestamp);
				$timestamp = $timestamp + $epoch;
			}

			$trip = sanitize($data['trip']);

			if ($trip == 0) {

				mysqli_query($conn, "
					INSERT INTO gps_car_init (imei, date) VALUES ('$imei', '$now');
				");

				$last_trip_query = select_query("
					SELECT trip, engine_status 
					FROM gps WHERE id=(
						SELECT MAX(`id`) AS max_id 
						FROM gps 
						WHERE imei='$imei'
					);
				");

				$last_trip = $last_trip_query[0]['trip'];
				$last_engine_status = $last_trip_query[0]['engine_status'];

				if (count($last_trip_query) == 0) { $trip = 1; } 
				else {
					//NO ENGINE CONTROL
					if ($version == 0.1) {
						$trip = $last_trip + 1;
					} 
					//WITH ENGINE CONTROL
					elseif ($version == 0.2) {
						if ($last_engine_status=='off') { $trip = $last_trip + 1; }
						else { $trip = $last_trip; }
					}
				}
			}

			$lat = sanitize($data['lat']);
			$lng = sanitize($data['lng']);
			$speed = sanitize($data['speed']);
			$satellites = sanitize($data['sats']);
			$grps = sanitize($data['2g']);
			$car_status = sanitize($data['cstat']);

			mysqli_query($conn, "
				INSERT INTO gps (version, imei, trip, counter, timestamp, date, data_type, lat, lng, speed, gprs, satellites, engine_status) 
				VALUES ($version, '$imei', $trip, $gps_counter ,'$timestamp', '$now', '$data_type', '$lat', '$lng', $speed, $grps, $satellites, '$car_status');
			");
		}

		if (http_response_code(200)) {

			$sql = mysqli_query($conn, "SELECT osSleep, version, post_error FROM devices WHERE imei='$imei'");
			$result = $sql->fetch_assoc();
			if ($speed > 90) { $sleep = 15; } 
			else { $sleep = $result['osSleep']; }

			echo $result['version'] . ":" . $sleep . ":" . $trip . ":" . $result['post_error'];

		} else { echo("ERROR"); }

	} else {
		
		//POST ERRORS IN MODULE
		if (in_array("SCbi4yaHBO", $json_object)) {

			$imei = $json_object[0];
			$datetime = time();
			$now = date("Y-m-d H:i:s", $datetime);

			for ($i=1; $i < count($json_object) - 1; $i++) {

				if ($json_object[$i]!="") {
					$error = $json_object[$i];
					mysqli_query($conn, "INSERT INTO errors (imei, date, error) VALUES ('$imei', '$now', '$error')");
				}

			}
			
			if (http_response_code(200)) {
				mysqli_query($conn, "UPDATE devices SET post_error=0 WHERE imei='$imei'");
				echo "OK";
			}
		}
	}

?>