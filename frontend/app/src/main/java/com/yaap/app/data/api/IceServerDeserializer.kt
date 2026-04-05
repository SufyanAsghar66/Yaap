package com.yaap.app.data.api

import com.google.gson.JsonDeserializationContext
import com.google.gson.JsonDeserializer
import com.google.gson.JsonElement
import com.yaap.app.model.IceServer
import java.lang.reflect.Type

/**
 * Django returns STUN entries as `{ "urls": "stun:..." }` (string) and TURN as objects;
 * this normalizes to [IceServer.urls] as a list of strings for the WebRTC client.
 */
class IceServerDeserializer : JsonDeserializer<IceServer> {
    override fun deserialize(json: JsonElement, typeOfT: Type, context: JsonDeserializationContext): IceServer {
        val o = json.asJsonObject
        val urlsEl = o.get("urls")
        val urls: List<String> = when {
            urlsEl == null || urlsEl.isJsonNull -> emptyList()
            urlsEl.isJsonPrimitive -> listOf(urlsEl.asString)
            urlsEl.isJsonArray -> urlsEl.asJsonArray.map { it.asString }
            else -> emptyList()
        }
        val username = o.get("username")?.takeIf { !it.isJsonNull }?.asString
        val credential = o.get("credential")?.takeIf { !it.isJsonNull }?.asString
        return IceServer(urls, username, credential)
    }
}
