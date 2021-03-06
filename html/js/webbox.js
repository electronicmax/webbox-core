/*
    This file is part of WebBox.

    Copyright 2012 Daniel Alexander Smith
    Copyright 2012 University of Southampton

    WebBox is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    WebBox is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with WebBox.  If not, see <http://www.gnu.org/licenses/>.
*/

// convert sparql results format into a format that DynamicTable can read
function wb_results_to_data(results, pred_map){
    // pred_map is {"result_var": "pred_uri"}
    var results_out = {};
    $.each(results['results']['bindings'], function(){
        var result = this
        var new_result = {};
        var uri = null;
        $.each(result, function(key, val_hsh){
            var val = val_hsh['value'];
            var typ = val_hsh['type'];
            var pred = key;
            if (key in pred_map){
                pred = pred_map[key];
            }
            if (pred == "uri"){
                uri = val;
            }
            new_result[pred] = [val_hsh]; // in an array because DynamicTable support multiple values per predicate
        });
        if (uri != null){
            if (!(uri in results_out)){
                results_out[uri] = [];
            }
            results_out[uri].push(new_result);
        }
    });
    return results_out;
}

function wb_json_normalise(data){
    var newdata = {};

//    console.debug("data", data);

    var item_map = function(item){
        var newitem = {};
        if ("@id" in item){
            $.each(item, function(key, val){
                if (key == "@type"){
                    if (typeof val === "string"){
                        newitem["rdf:type"] = "<"+val+">";
                    } else {
                        if (!("rdf:type" in newitem)){
                            newitem["rdf:type"] = [];
                        }
                        $.each(val, function(){
                            newitem["rdf:type"].push("<"+this+">");
                        });
                    }

                } else if (key === "@id"){
                    // do nothing
                } else {
                    if (typeof val === "string"){
                        newitem[key] = "\""+val+"\"";
                    } else {
                        newitem[key] = "<"+val["@value"]+">";
                    }
                }
            });
        }
        return newitem;
    };

    if ("@graph" in data){
        $.each(data["@graph"], function(){
            var item = this;
            var newitem = item_map(item);
            var id = item["@id"];
            newitem["uri"] = "<"+id+">";
            newdata[id] = newitem;
        });
    } else {
        var item = data;

        if ("@context" in item){
            delete item["@context"];
        }

        var newitem = item_map(item);
        var id = item["@id"];
        newitem["uri"] = "<"+id+">";
        newdata[id] = newitem;
    }

//    console.debug("newdata", newdata);

    return newdata;
}
