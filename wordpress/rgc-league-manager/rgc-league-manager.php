<?php
/**
 * Plugin Name: RGC League Manager
 * Description: Publishes RGC AI Broadcast Studio league schedules, results, standings, and driver statistics.
 * Version: 0.3.0
 * Author: Realistic Gaming Crew
 * License: GPL-2.0-or-later
 */

if (!defined('ABSPATH')) { exit; }

define('RGCLM_VERSION', '0.3.0');

function rgclm_tables() {
    global $wpdb;
    return [
        'leagues' => $wpdb->prefix . 'rgclm_leagues',
        'seasons' => $wpdb->prefix . 'rgclm_seasons',
        'events' => $wpdb->prefix . 'rgclm_events',
        'results' => $wpdb->prefix . 'rgclm_results',
    ];
}

function rgclm_activate() {
    global $wpdb;
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    $t = rgclm_tables();
    $charset = $wpdb->get_charset_collate();
    dbDelta("CREATE TABLE {$t['leagues']} (
        id bigint unsigned NOT NULL AUTO_INCREMENT,
        slug varchar(100) NOT NULL,
        name varchar(200) NOT NULL,
        short_name varchar(80) NOT NULL DEFAULT '',
        updated_at datetime NOT NULL,
        PRIMARY KEY (id), UNIQUE KEY slug (slug)
    ) $charset;");
    dbDelta("CREATE TABLE {$t['seasons']} (
        id bigint unsigned NOT NULL AUTO_INCREMENT,
        league_id bigint unsigned NOT NULL,
        slug varchar(100) NOT NULL,
        name varchar(200) NOT NULL,
        updated_at datetime NOT NULL,
        PRIMARY KEY (id), UNIQUE KEY league_season (league_id,slug), KEY league_id (league_id)
    ) $charset;");
    dbDelta("CREATE TABLE {$t['events']} (
        id bigint unsigned NOT NULL AUTO_INCREMENT,
        season_id bigint unsigned NOT NULL,
        round_number int NOT NULL,
        event_date varchar(20) NOT NULL DEFAULT '',
        event_name varchar(200) NOT NULL DEFAULT '',
        track_name varchar(200) NOT NULL DEFAULT '',
        configuration varchar(200) NOT NULL DEFAULT '',
        car_type varchar(160) NOT NULL DEFAULT '',
        laps int NULL,
        duration_minutes int NULL,
        practice_time varchar(20) NOT NULL DEFAULT '',
        qualifying_time varchar(20) NOT NULL DEFAULT '',
        race_time varchar(20) NOT NULL DEFAULT '',
        status varchar(40) NOT NULL DEFAULT 'Scheduled',
        notes text NULL,
        updated_at datetime NOT NULL,
        PRIMARY KEY (id), UNIQUE KEY season_round (season_id,round_number), KEY season_id (season_id)
    ) $charset;");
    dbDelta("CREATE TABLE {$t['results']} (
        id bigint unsigned NOT NULL AUTO_INCREMENT,
        event_id bigint unsigned NOT NULL,
        driver_key varchar(190) NOT NULL,
        position int NOT NULL,
        name varchar(200) NOT NULL,
        car_number varchar(30) NOT NULL DEFAULT '',
        starting_position int NULL,
        laps_completed int NOT NULL DEFAULT 0,
        laps_led int NOT NULL DEFAULT 0,
        fastest_lap decimal(12,3) NULL,
        incidents int NULL,
        status varchar(80) NOT NULL DEFAULT '',
        points decimal(12,3) NOT NULL DEFAULT 0,
        team_name varchar(200) NOT NULL DEFAULT '',
        country_code varchar(12) NOT NULL DEFAULT '',
        average_lap decimal(12,3) NULL,
        race_interval varchar(40) NOT NULL DEFAULT '',
        position_points decimal(12,3) NOT NULL DEFAULT 0,
        bonus_points decimal(12,3) NOT NULL DEFAULT 0,
        penalty_points decimal(12,3) NOT NULL DEFAULT 0,
        stage_points decimal(12,3) NOT NULL DEFAULT 0,
        time_penalty_seconds decimal(12,3) NOT NULL DEFAULT 0,
        lap_penalty_laps int NOT NULL DEFAULT 0,
        manual_adjustment decimal(12,3) NOT NULL DEFAULT 0,
        adjustment_reason varchar(255) NOT NULL DEFAULT '',
        updated_at datetime NOT NULL,
        PRIMARY KEY (id), UNIQUE KEY event_driver (event_id,driver_key), KEY event_id (event_id)
    ) $charset;");
    update_option('rgclm_db_version', RGCLM_VERSION);
}
register_activation_hook(__FILE__, 'rgclm_activate');
function rgclm_maybe_upgrade() {
    if (get_option('rgclm_db_version') !== RGCLM_VERSION) { rgclm_activate(); }
}
add_action('plugins_loaded', 'rgclm_maybe_upgrade');

function rgclm_slug($value, $fallback = 'league') {
    $slug = sanitize_title((string) $value);
    return $slug ?: $fallback;
}

function rgclm_number_or_null($value, $integer = true) {
    if ($value === '' || $value === null) { return null; }
    return $integer ? intval($value) : floatval($value);
}

function rgclm_register_routes() {
    register_rest_route('rgc-league-manager/v1', '/sync', [
        'methods' => 'POST',
        'callback' => 'rgclm_sync',
        'permission_callback' => function () { return current_user_can('manage_options'); },
    ]);
    register_rest_route('rgc-league-manager/v1', '/leagues', [
        'methods' => 'GET', 'callback' => 'rgclm_api_leagues', 'permission_callback' => '__return_true',
    ]);
    register_rest_route('rgc-league-manager/v1', '/league/(?P<slug>[a-z0-9-]+)', [
        'methods' => 'GET', 'callback' => 'rgclm_api_league', 'permission_callback' => '__return_true',
    ]);
}
add_action('rest_api_init', 'rgclm_register_routes');

function rgclm_sync(WP_REST_Request $request) {
    global $wpdb;
    $data = $request->get_json_params();
    if (!is_array($data) || empty($data['league']['name'])) {
        return new WP_Error('rgclm_bad_payload', 'The payload must include league.name.', ['status' => 400]);
    }
    $t = rgclm_tables();
    $now = current_time('mysql');
    $league = $data['league'];
    $league_slug = rgclm_slug($league['slug'] ?? $league['name']);
    $league_row = [
        'slug' => $league_slug,
        'name' => sanitize_text_field($league['name']),
        'short_name' => sanitize_text_field($league['short_name'] ?? ''),
        'updated_at' => $now,
    ];
    $league_id = intval($wpdb->get_var($wpdb->prepare("SELECT id FROM {$t['leagues']} WHERE slug=%s", $league_slug)));
    if ($league_id) { $wpdb->update($t['leagues'], $league_row, ['id'=>$league_id]); }
    else { $wpdb->insert($t['leagues'], $league_row); $league_id = intval($wpdb->insert_id); }
    $season = is_array($data['season'] ?? null) ? $data['season'] : [];
    $season_name = sanitize_text_field($season['name'] ?? 'Current Season');
    $season_slug = rgclm_slug($season['slug'] ?? $season_name, 'current-season');
    $season_id = intval($wpdb->get_var($wpdb->prepare("SELECT id FROM {$t['seasons']} WHERE league_id=%d AND slug=%s", $league_id, $season_slug)));
    $season_row = ['league_id'=>$league_id, 'slug'=>$season_slug, 'name'=>$season_name, 'updated_at'=>$now];
    if ($season_id) { $wpdb->update($t['seasons'], $season_row, ['id'=>$season_id]); }
    else { $wpdb->insert($t['seasons'], $season_row); $season_id = intval($wpdb->insert_id); }

    foreach ((array) ($data['schedule'] ?? []) as $item) {
        $round = intval($item['round_number'] ?? 0);
        if ($round < 1) { continue; }
        $row = [
            'season_id'=>$season_id, 'round_number'=>$round,
            'event_date'=>sanitize_text_field($item['event_date'] ?? ''),
            'event_name'=>sanitize_text_field($item['event_name'] ?? ''),
            'track_name'=>sanitize_text_field($item['track_name'] ?? ''),
            'configuration'=>sanitize_text_field($item['configuration'] ?? ''),
            'car_type'=>sanitize_text_field($item['car_type'] ?? ''),
            'laps'=>rgclm_number_or_null($item['laps'] ?? null),
            'duration_minutes'=>rgclm_number_or_null($item['duration_minutes'] ?? null),
            'practice_time'=>sanitize_text_field($item['practice_time'] ?? ''),
            'qualifying_time'=>sanitize_text_field($item['qualifying_time'] ?? ''),
            'race_time'=>sanitize_text_field($item['race_time'] ?? ''),
            'status'=>sanitize_text_field($item['status'] ?? 'Scheduled'),
            'notes'=>sanitize_textarea_field($item['notes'] ?? ''), 'updated_at'=>$now,
        ];
        $event_id = intval($wpdb->get_var($wpdb->prepare("SELECT id FROM {$t['events']} WHERE season_id=%d AND round_number=%d", $season_id, $round)));
        if ($event_id) { $wpdb->update($t['events'], $row, ['id'=>$event_id]); }
        else { $wpdb->insert($t['events'], $row); }
    }

    foreach ((array) ($data['results'] ?? []) as $race) {
        $round = intval($race['round_number'] ?? 0);
        $event_id = intval($wpdb->get_var($wpdb->prepare("SELECT id FROM {$t['events']} WHERE season_id=%d AND round_number=%d", $season_id, $round)));
        if (!$event_id) { continue; }
        $wpdb->delete($t['results'], ['event_id'=>$event_id], ['%d']);
        foreach ((array) ($race['entries'] ?? []) as $entry) {
            $name = sanitize_text_field($entry['name'] ?? '');
            if (!$name) { continue; }
            $number = sanitize_text_field($entry['car_number'] ?? '');
            $wpdb->insert($t['results'], [
                'event_id'=>$event_id,
                'driver_key'=>substr(hash('sha256', strtolower(trim($name)).'|'.$number), 0, 40),
                'position'=>intval($entry['position'] ?? 0), 'name'=>$name, 'car_number'=>$number,
                'starting_position'=>rgclm_number_or_null($entry['starting_position'] ?? null),
                'laps_completed'=>intval($entry['laps_completed'] ?? 0),
                'laps_led'=>intval($entry['laps_led'] ?? 0),
                'fastest_lap'=>rgclm_number_or_null($entry['fastest_lap'] ?? null, false),
                'incidents'=>rgclm_number_or_null($entry['incidents'] ?? null),
                'status'=>sanitize_text_field($entry['status'] ?? ''),
                'points'=>floatval($entry['points'] ?? 0), 'updated_at'=>$now,
                'team_name'=>sanitize_text_field($entry['team_name'] ?? ''),
                'country_code'=>sanitize_text_field($entry['country_code'] ?? ''),
                'average_lap'=>rgclm_number_or_null($entry['average_lap'] ?? null, false),
                'race_interval'=>sanitize_text_field($entry['interval'] ?? ''),
                'position_points'=>floatval($entry['position_points'] ?? 0),
                'bonus_points'=>floatval($entry['bonus_points'] ?? 0),
                'penalty_points'=>floatval($entry['penalty_points'] ?? 0),
                'stage_points'=>floatval($entry['stage_points'] ?? 0),
                'time_penalty_seconds'=>floatval($entry['time_penalty_seconds'] ?? 0),
                'lap_penalty_laps'=>intval($entry['lap_penalty_laps'] ?? 0),
                'manual_adjustment'=>floatval($entry['manual_adjustment'] ?? 0),
                'adjustment_reason'=>sanitize_text_field($entry['adjustment_reason'] ?? ''),
            ]);
        }
        $wpdb->update($t['events'], ['status'=>'Completed','updated_at'=>$now], ['id'=>$event_id]);
    }
    return rest_ensure_response(['ok'=>true, 'league'=>$league_slug, 'season'=>$season_slug]);
}

function rgclm_api_leagues() {
    global $wpdb; $t=rgclm_tables();
    return rest_ensure_response($wpdb->get_results("SELECT slug,name,short_name,updated_at FROM {$t['leagues']} ORDER BY name", ARRAY_A));
}

function rgclm_dataset($league_slug) {
    global $wpdb; $t=rgclm_tables();
    $league=$wpdb->get_row($wpdb->prepare("SELECT * FROM {$t['leagues']} WHERE slug=%s", $league_slug), ARRAY_A);
    if (!$league) { return null; }
    $season=$wpdb->get_row($wpdb->prepare("SELECT * FROM {$t['seasons']} WHERE league_id=%d ORDER BY id DESC LIMIT 1", $league['id']), ARRAY_A);
    if (!$season) { return ['league'=>$league,'season'=>null,'schedule'=>[],'results'=>[],'standings'=>[]]; }
    $events=$wpdb->get_results($wpdb->prepare("SELECT * FROM {$t['events']} WHERE season_id=%d ORDER BY round_number", $season['id']), ARRAY_A);
    $results=[];
    foreach ($events as $event) {
        $entries=$wpdb->get_results($wpdb->prepare("SELECT * FROM {$t['results']} WHERE event_id=%d ORDER BY position", $event['id']), ARRAY_A);
        if ($entries) { $results[]=['round_number'=>intval($event['round_number']),'event'=>$event,'entries'=>$entries]; }
    }
    return ['league'=>$league,'season'=>$season,'schedule'=>$events,'results'=>$results,'standings'=>rgclm_standings($results)];
}

function rgclm_standings($races) {
    $drivers=[];
    foreach ($races as $race) foreach ($race['entries'] as $e) {
        $key=strtolower(trim($e['name'])).'|'.$e['car_number'];
        if (!isset($drivers[$key])) $drivers[$key]=['name'=>$e['name'],'car_number'=>$e['car_number'],'starts'=>0,'wins'=>0,'top_fives'=>0,'top_tens'=>0,'laps_led'=>0,'points'=>0.0,'finish_total'=>0];
        $d=&$drivers[$key]; $pos=intval($e['position']);
        $d['starts']++; $d['wins'] += ($pos===1); $d['top_fives'] += ($pos<=5); $d['top_tens'] += ($pos<=10);
        $d['laps_led'] += intval($e['laps_led']); $d['points'] += floatval($e['points']); $d['finish_total'] += $pos;
    }
    foreach ($drivers as &$d) { $d['average_finish']=$d['starts'] ? round($d['finish_total']/$d['starts'],2) : 0; unset($d['finish_total']); }
    usort($drivers, function($a,$b){
        if ($a['points'] != $b['points']) return $b['points'] <=> $a['points'];
        if ($a['wins'] != $b['wins']) return $b['wins'] <=> $a['wins'];
        return $a['average_finish'] <=> $b['average_finish'];
    });
    return array_values($drivers);
}

function rgclm_api_league(WP_REST_Request $request) {
    $data=rgclm_dataset(sanitize_title($request['slug']));
    return $data ? rest_ensure_response($data) : new WP_Error('rgclm_not_found','League not found.',['status'=>404]);
}

function rgclm_table($headers, $rows) {
    $html='<div class="rgclm-table-wrap"><table class="rgclm-table"><thead><tr>';
    foreach ($headers as $header) $html.='<th>'.esc_html($header).'</th>';
    $html.='</tr></thead><tbody>';
    foreach ($rows as $row) { $html.='<tr>'; foreach ($row as $cell) $html.='<td>'.esc_html((string)$cell).'</td>'; $html.='</tr>'; }
    return $html.'</tbody></table></div>';
}

function rgclm_shortcode($atts) {
    $atts=shortcode_atts(['league'=>'','view'=>'all'], $atts, 'rgc_league_manager');
    $data=rgclm_dataset(sanitize_title($atts['league']));
    if (!$data) return '<p class="rgclm-empty">League data has not been published yet.</p>';
    wp_enqueue_style('rgclm-public', plugins_url('assets/league-manager.css', __FILE__), [], RGCLM_VERSION);
    ob_start(); ?>
    <section class="rgclm" data-league="<?php echo esc_attr($data['league']['slug']); ?>">
      <header class="rgclm-hero"><p>RGC LEAGUE MANAGER</p><h2><?php echo esc_html($data['league']['name']); ?></h2><span><?php echo esc_html($data['season']['name'] ?? 'Current Season'); ?></span></header>
      <nav class="rgclm-tabs"><button data-tab="standings">Standings</button><button data-tab="schedule">Schedule</button><button data-tab="results">Results</button><button data-tab="drivers">Drivers</button></nav>
      <div class="rgclm-panel" data-panel="standings"><?php
        $rows=[]; foreach($data['standings'] as $i=>$d) $rows[]=[($i+1), '#'.$d['car_number'], $d['name'], $d['starts'], $d['wins'], $d['top_fives'], $d['top_tens'], $d['laps_led'], number_format($d['points'],1)];
        echo rgclm_table(['Pos','No.','Driver','Starts','Wins','Top 5','Top 10','Laps Led','Points'],$rows); ?></div>
      <div class="rgclm-panel" data-panel="schedule" hidden><?php
        $rows=[]; foreach($data['schedule'] as $e) $rows[]=[$e['round_number'],$e['event_date'],$e['event_name'],$e['track_name'],trim($e['configuration'].' '.$e['car_type']),$e['laps'] ?: ($e['duration_minutes'].' min'),$e['practice_time'],$e['qualifying_time'],$e['race_time'],$e['status']];
        echo rgclm_table(['Rd','Date','Race','Track','Car / Configuration','Distance','Practice','Qualifying','Race','Status'],$rows); ?></div>
      <div class="rgclm-panel" data-panel="results" hidden><?php foreach(array_reverse($data['results']) as $race) {
        echo '<h3>Round '.intval($race['round_number']).' — '.esc_html($race['event']['event_name']).'</h3>';
        $rows=[]; foreach($race['entries'] as $e) $rows[]=[$e['position'],'#'.$e['car_number'],$e['name'].($e['team_name'] ? ' — '.$e['team_name'] : ''),$e['starting_position'] ?: '—',$e['laps_completed'],$e['laps_led'],$e['fastest_lap'] ?: '—',$e['incidents'] === null ? '—' : $e['incidents'],number_format((float)$e['points'],1)];
        echo rgclm_table(['Finish','No.','Driver / Team','Start','Laps','Led','Best Lap','Inc','Points'],$rows);
      } ?></div>
      <div class="rgclm-panel" data-panel="drivers" hidden><?php
        $rows=[]; foreach($data['standings'] as $d) $rows[]=['#'.$d['car_number'],$d['name'],$d['starts'],$d['wins'],number_format($d['average_finish'],2),$d['laps_led']];
        echo rgclm_table(['No.','Driver','Starts','Wins','Avg Finish','Laps Led'],$rows); ?></div>
    </section>
    <script>document.currentScript.previousElementSibling.querySelectorAll('.rgclm-tabs button').forEach(function(b){b.addEventListener('click',function(){var root=b.closest('.rgclm');root.querySelectorAll('.rgclm-panel').forEach(function(p){p.hidden=p.dataset.panel!==b.dataset.tab});root.querySelectorAll('.rgclm-tabs button').forEach(function(x){x.classList.toggle('active',x===b)})})});document.currentScript.previousElementSibling.querySelector('.rgclm-tabs button').classList.add('active');</script>
    <?php return ob_get_clean();
}
add_shortcode('rgc_league_manager', 'rgclm_shortcode');

function rgclm_admin_menu() { add_management_page('RGC League Manager','RGC League Manager','manage_options','rgc-league-manager','rgclm_admin_page'); }
add_action('admin_menu','rgclm_admin_menu');
function rgclm_admin_page() { ?>
  <div class="wrap"><h1>RGC League Manager</h1><p>The plugin is ready to receive League Manager data from RGC AI Broadcast Studio.</p>
  <h2>Connection</h2><p>Endpoint: <code><?php echo esc_html(rest_url('rgc-league-manager/v1/sync')); ?></code></p>
  <p>Create a dedicated WordPress administrator account and an Application Password under <strong>Users → Profile → Application Passwords</strong>. Use HTTPS.</p>
  <h2>Display</h2><p>Add this shortcode to a WordPress page:</p><code>[rgc_league_manager league="your-league-slug"]</code>
  <p>Use the public API at <code><?php echo esc_html(rest_url('rgc-league-manager/v1/leagues')); ?></code> to list published leagues.</p></div>
<?php }
