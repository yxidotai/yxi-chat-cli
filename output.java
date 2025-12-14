package com.example.demo;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.*;

@JsonIgnoreProperties(ignoreUnknown = true)
public static class Root {
    @JsonProperty("v01")
    public String v01;
    @JsonProperty("v02")
    public Double v02;
    @JsonProperty("v03")
    public V03 v03;
    @JsonProperty("v04")
    public java.util.List<V04item2> v04;
}

@JsonIgnoreProperties(ignoreUnknown = true)
public static class V04item2 {
    @JsonProperty("v01")
    public String v01;
    @JsonProperty("v02")
    public Double v02;
    @JsonProperty("v03")
    public V033 v03;
    @JsonProperty("v04")
    public java.util.List<V04item3> v04;
}

@JsonIgnoreProperties(ignoreUnknown = true)
public static class V04item3 {
    @JsonProperty("v01")
    public String v01;
    @JsonProperty("v02")
    public Double v02;
    @JsonProperty("v03")
    public Object v03;
    @JsonProperty("v04")
    public java.util.List<String> v04;
}

@JsonIgnoreProperties(ignoreUnknown = true)
public static class V033 {
    @JsonProperty("v01")
    public String v01;
    @JsonProperty("v02")
    public Double v02;
    @JsonProperty("v03")
    public Object v03;
    @JsonProperty("v04")
    public java.util.List<String> v04;
}

@JsonIgnoreProperties(ignoreUnknown = true)
public static class V03 {
    @JsonProperty("v01")
    public String v01;
    @JsonProperty("v02")
    public Double v02;
    @JsonProperty("v03")
    public V032 v03;
    @JsonProperty("v04")
    public java.util.List<V04item> v04;
}

@JsonIgnoreProperties(ignoreUnknown = true)
public static class V04item {
    @JsonProperty("v01")
    public String v01;
    @JsonProperty("v02")
    public Double v02;
    @JsonProperty("v03")
    public Object v03;
    @JsonProperty("v04")
    public java.util.List<String> v04;
}

@JsonIgnoreProperties(ignoreUnknown = true)
public static class V032 {
    @JsonProperty("v01")
    public String v01;
    @JsonProperty("v02")
    public Double v02;
    @JsonProperty("v03")
    public Object v03;
    @JsonProperty("v04")
    public java.util.List<String> v04;
}