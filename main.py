from flask import Flask, render_template
import json
from bs4 import BeautifulSoup
 
import requests
import gspread
import json
from apscheduler.schedulers.background import BackgroundScheduler
display_positions=[]
cric_score_1 = None
cric_score_2 = None

with open('config.json') as jFile:
    jdata = json.load(jFile)
    url = jdata[0]["url"]
    # urlapi = jdata[1]["urlapi"]
    # OR
    urlapi = jdata[6]["urlapi1"]
    n1 = jdata[2]["n1"]
    n2 = jdata[3]["n2"]
    time_to_load = jdata[4]["t"]
    runnings = jdata[5]["runnings"]
    
def timed_job():
    # print('This job is run every five minutes.')
    # *********** Cric Score *****************
    response = requests.get(url)
    htmlContent = response.content
    mySoup = BeautifulSoup(htmlContent, 'html.parser')
    global cric_score_1
    # cric_score_1=list(mySoup.stripped_strings)[n1]
    cric_score_1= "Mi - 159/9(20)"
    global cric_score_2
    # cric_score_2=list(mySoup.stripped_strings)[n2]
    cric_score_2= "RCB - 160/8(20)"
    
    # *********** Cric Api Data *****************
    cric_data = requests.get(urlapi)
    json_cric_data = cric_data.json()

    # *********** Id to Score Mapping *****************
    def player_score(player_id):
        player_net_score = 0
        field = json_cric_data["data"]["fielding"]
        bowl = json_cric_data["data"]["bowling"]
        bat = json_cric_data["data"]["batting"]
        for i in range(len(field)): # 2
            field_deep = field[i]["scores"]
            for j in range(len(field_deep)):
                if player_id == int(field_deep[j]["pid"]):
                    player_net_score+= int(field_deep[j]["catch"])*8 + int(field_deep[j]["stumped"])*12 + int(field_deep[j]["runout"])*12
        for i in range(len(bowl)):
            bowl_deep = bowl[i]["scores"]
            for j in range(len(bowl_deep)):
                if player_id == int(bowl_deep[j]["pid"]):
                    player_net_score+= int(bowl_deep[j]["W"])*20
                    if int(bowl_deep[j]["W"]) >= 5:
                        player_net_score+=16
                    elif int(bowl_deep[j]["W"]) >= 4:
                        player_net_score+=8
        for i in range(len(bat)):
            bat_deep = bat[i]["scores"]
            for j in range(len(bat_deep)):
                if player_id == int(bat_deep[j]["pid"]):
                    player_net_score+= int(bat_deep[j]["R"])
                    if int(bat_deep[j]["R"]) >= 100:
                        player_net_score+=16
                    elif int(bat_deep[j]["R"]) >= 50:
                        player_net_score+=8
                    elif int(bat_deep[j]["R"]) >= 30:
                        player_net_score+=4
        return player_net_score    
    id_to_score_list = []
    def append_to_player_id_list(json_cric_data):
        for i in range(len(json_cric_data["data"]["team"])):   # 2
            teamPlaying = json_cric_data["data"]["team"][i]["players"]
            for j in range(len(teamPlaying)):  #  11
                myDict = {}
                myDict[int(teamPlaying[j]["pid"])] = player_score(int(teamPlaying[j]["pid"]))
                id_to_score_list.append(myDict)            
    append_to_player_id_list(json_cric_data)
    # print(id_to_score_list)

    # *********** Spreadsheet Response *****************
    myGspread = gspread.service_account(filename='credentials.json')
    sheet = myGspread.open_by_key('1vhIneGtte9JeT_7vnsaB2m7FugyxjlKuLS4PH75gxjs')
    worksheet = sheet.sheet1
    responses = worksheet.get_all_records()

    # *********** Append score to entries *****************
    def get_id(name):
        for i in range(len(json_cric_data["data"]["team"])):   # 2
            teamPlaying = json_cric_data["data"]["team"][i]["players"]
            for j in range(len(teamPlaying)):  #  11
                if name == teamPlaying[j]["name"]:
                    return int(teamPlaying[j]["pid"]) 
    def ret_score(playerId):
        for i in range(len(id_to_score_list)):
            if playerId in id_to_score_list[i].keys():
                return id_to_score_list[i][playerId]
        else:
            return 0
    def append_score(responses):
        for i in range(len(responses)):
            score = 0
            get_player_wise_scores = []
            del responses[i]["Timestamp"]
            del responses[i]["Email"]
            responses[i]["Gold Players"] = responses[i]["Gold Players"].split(", ")
            responses[i]["Silver Players"] = responses[i]["Silver Players"].split(", ")
            responses[i]["Bronze Players"] = responses[i]["Bronze Players"].split(", ")
            for j in range(len(responses[i]["Gold Players"])):
                get_player_wise_scores.append([ responses[i]["Gold Players"][j], ret_score(get_id(responses[i]["Gold Players"][j])) ])
                # print(responses[i]["Gold Players "][j])
            for j in range(len(responses[i]["Silver Players"])):
                get_player_wise_scores.append([responses[i]["Silver Players"][j], ret_score(get_id(responses[i]["Silver Players"][j])) ])
                # print(responses[i]["Silver Players "][j])
            for j in range(len(responses[i]["Bronze Players"])):
                get_player_wise_scores.append([responses[i]["Bronze Players"][j], ret_score(get_id(responses[i]["Bronze Players"][j])) ])
                # print(responses[i]["Bronze Players "][j])
            for j in range(len(get_player_wise_scores)):
                if get_player_wise_scores[j][0] == responses[i]["Captain (2x)"]:
                    get_player_wise_scores[j][0] += ' (𝐂)'
                    get_player_wise_scores[j][1]*=2
                    break
            for j in range(len(get_player_wise_scores)):
                if get_player_wise_scores[j][0] == responses[i]["Vice Captain (1.5x)"]:
                    get_player_wise_scores[j][0] += ' (𝐕𝐂)'
                    get_player_wise_scores[j][1]*=1.5
                    break
            for j in range(len(get_player_wise_scores)):
                score+=get_player_wise_scores[j][1]
            responses[i]["Player Wise Score"] = get_player_wise_scores
            responses[i]["Total Score"] = score
    append_score(responses)
    global display_positions
    display_positions = sorted(responses,key=lambda k: k['Total Score'], reverse=True)
    # print(display_positions)
        
        
if runnings:
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(timed_job,'interval',minutes=time_to_load)
    sched.start()
    
timed_job()
    
# Flask app
app = Flask(__name__)
@app.route('/', methods=['GET'])
def hello_world():
    return render_template('compact-table.html', teams = display_positions, score1 =cric_score_1, score2=cric_score_2)

if __name__ == "__main__":
    app.run(debug=True, use_debugger=False, use_reloader=False, port=8000)