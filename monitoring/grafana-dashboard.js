
{
  "apiVersion": "dashboard.grafana.app/v2",
  "kind": "Dashboard",
  "metadata": {
    "name": "suvw4zm",
    "namespace": "stacks-1907731",
    "uid": "5450386b-b008-45ca-8a5c-b7e68e23a5e8",
    "resourceVersion": "2125391229065048064",
    "generation": 25,
    "creationTimestamp": "2026-11-05T13:49:29Z",
    "labels": {
      "grafana.app/deprecatedInternalID": "1648098749890560"
    },
    "annotations": {
      "grafana.app/createdBy": "user:eg3dt1bmh04jkb",
      "grafana.app/saved-from-ui": "Grafana Cloud",
      "grafana.app/updatedBy": "user:eg3dt1bmh04jkb",
      "grafana.app/updatedTimestamp": "2026-11-25T00:48:51Z"
    }
  },
  "spec": {
    "annotations": [
      {
        "kind": "AnnotationQuery",
        "spec": {
          "query": {
            "kind": "DataQuery",
            "group": "grafana",
            "version": "v0",
            "datasource": {
              "name": "-- Grafana --"
            },
            "spec": {}
          },
          "enable": true,
          "hide": true,
          "iconColor": "rgba(0, 211, 255, 1)",
          "name": "Annotations & Alerts",
          "builtIn": true
        }
      }
    ],
    "cursorSync": "Off",
    "description": "Monitoring dashboard for the Drone Detection Cloud Computing project. Tracks Raspberry Pi cluster health (CPU, memory, temperature, network, and node availability), AI detection performance, inference latency, and system alerts.",
    "editable": true,
    "elements": {
      "panel-1": {
        "kind": "Panel",
        "spec": {
          "id": 1,
          "title": "Raspberry Pi – CPU Usage (%)",
          "description": "Monitoring dashboard for the Drone Detection Cloud Computing project. Tracks Raspberry Pi cluster health (CPU, memory, temperature, network, and node availability), AI detection performance, inference latency, and system alerts.\n Copy",
          "links": [],
          "data": {
            "kind": "QueryGroup",
            "spec": {
              "queries": [
                {
                  "kind": "PanelQuery",
                  "spec": {
                    "query": {
                      "kind": "DataQuery",
                      "group": "prometheus",
                      "version": "v0",
                      "datasource": {
                        "name": "grafanacloud-prom"
                      },
                      "spec": {
                        "editorMode": "code",
                        "expr": "100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{job=\"node\",mode=\"idle\"}[5m])))",
                        "legendFormat": "{{instance}}",
                        "range": true
                      }
                    },
                    "refId": "A",
                    "hidden": false
                  }
                }
              ],
              "transformations": [],
              "queryOptions": {}
            }
          },
          "vizConfig": {
            "kind": "VizConfig",
            "group": "timeseries",
            "version": "13.4.0-44730370174",
            "spec": {
              "options": {
                "legend": {
                  "calcs": [],
                  "displayMode": "list",
                  "placement": "bottom",
                  "showLegend": true
                },
                "tooltip": {
                  "hideZeros": false,
                  "mode": "single",
                  "sort": "none"
                }
              },
              "fieldConfig": {
                "defaults": {
                  "unit": "percent",
                  "thresholds": {
                    "mode": "absolute",
                    "steps": [
                      {
                        "value": 0,
                        "color": "green"
                      },
                      {
                        "value": 80,
                        "color": "red"
                      }
                    ]
                  },
                  "color": {
                    "mode": "palette-classic"
                  },
                  "custom": {
                    "axisBorderShow": false,
                    "axisCenteredZero": false,
                    "axisColorMode": "text",
                    "axisLabel": "",
                    "axisPlacement": "auto",
                    "barAlignment": 0,
                    "barWidthFactor": 0.6,
                    "drawStyle": "line",
                    "fillOpacity": 0,
                    "gradientMode": "none",
                    "hideFrom": {
                      "legend": false,
                      "tooltip": false,
                      "viz": false
                    },
                    "insertNulls": false,
                    "lineInterpolation": "linear",
                    "lineWidth": 1,
                    "pointSize": 5,
                    "scaleDistribution": {
                      "type": "linear"
                    },
                    "showPoints": "auto",
                    "showValues": false,
                    "spanNulls": false,
                    "stacking": {
                      "group": "A",
                      "mode": "none"
                    },
                    "thresholdsStyle": {
                      "mode": "off"
                    }
                  }
                },
                "overrides": []
              }
            }
          }
        }
      },
      "panel-2": {
        "kind": "Panel",
        "spec": {
          "id": 2,
          "title": "Raspberry Pi – RAM Usage (%)",
          "description": "",
          "links": [],
          "data": {
            "kind": "QueryGroup",
            "spec": {
              "queries": [
                {
                  "kind": "PanelQuery",
                  "spec": {
                    "query": {
                      "kind": "DataQuery",
                      "group": "prometheus",
                      "version": "v0",
                      "datasource": {
                        "name": "grafanacloud-prom"
                      },
                      "spec": {
                        "editorMode": "code",
                        "expr": "100 * (1 - (\n  node_memory_MemAvailable_bytes{job=\"node\"}\n  /\n  node_memory_MemTotal_bytes{job=\"node\"}\n))",
                        "legendFormat": "{{instance}}",
                        "range": true
                      }
                    },
                    "refId": "A",
                    "hidden": false
                  }
                }
              ],
              "transformations": [],
              "queryOptions": {}
            }
          },
          "vizConfig": {
            "kind": "VizConfig",
            "group": "timeseries",
            "version": "13.4.0-44730370174",
            "spec": {
              "options": {
                "legend": {
                  "calcs": [],
                  "displayMode": "list",
                  "placement": "bottom",
                  "showLegend": true
                },
                "tooltip": {
                  "hideZeros": false,
                  "mode": "single",
                  "sort": "none"
                }
              },
              "fieldConfig": {
                "defaults": {
                  "unit": "percent",
                  "thresholds": {
                    "mode": "absolute",
                    "steps": [
                      {
                        "value": 0,
                        "color": "green"
                      },
                      {
                        "value": 80,
                        "color": "red"
                      }
                    ]
                  },
                  "color": {
                    "mode": "palette-classic"
                  },
                  "custom": {
                    "axisBorderShow": false,
                    "axisCenteredZero": false,
                    "axisColorMode": "text",
                    "axisLabel": "",
                    "axisPlacement": "auto",
                    "barAlignment": 0,
                    "barWidthFactor": 0.6,
                    "drawStyle": "line",
                    "fillOpacity": 0,
                    "gradientMode": "none",
                    "hideFrom": {
                      "legend": false,
                      "tooltip": false,
                      "viz": false
                    },
                    "insertNulls": false,
                    "lineInterpolation": "linear",
                    "lineWidth": 1,
                    "pointSize": 5,
                    "scaleDistribution": {
                      "type": "linear"
                    },
                    "showPoints": "auto",
                    "showValues": false,
                    "spanNulls": false,
                    "stacking": {
                      "group": "A",
                      "mode": "none"
                    },
                    "thresholdsStyle": {
                      "mode": "off"
                    }
                  }
                },
                "overrides": []
              }
            }
          }
        }
      },
      "panel-3": {
        "kind": "Panel",
        "spec": {
          "id": 3,
          "title": "Raspberry Pi – CPU Temperature (°C)",
          "description": "",
          "links": [],
          "data": {
            "kind": "QueryGroup",
            "spec": {
              "queries": [
                {
                  "kind": "PanelQuery",
                  "spec": {
                    "query": {
                      "kind": "DataQuery",
                      "group": "prometheus",
                      "version": "v0",
                      "datasource": {
                        "name": "grafanacloud-prom"
                      },
                      "spec": {
                        "editorMode": "code",
                        "expr": "node_thermal_zone_temp{job=\"node\"}",
                        "legendFormat": "{{instance}}",
                        "range": true
                      }
                    },
                    "refId": "A",
                    "hidden": false
                  }
                }
              ],
              "transformations": [],
              "queryOptions": {}
            }
          },
          "vizConfig": {
            "kind": "VizConfig",
            "group": "timeseries",
            "version": "13.4.0-44730370174",
            "spec": {
              "options": {
                "legend": {
                  "calcs": [],
                  "displayMode": "list",
                  "placement": "bottom",
                  "showLegend": true
                },
                "tooltip": {
                  "hideZeros": false,
                  "mode": "single",
                  "sort": "none"
                }
              },
              "fieldConfig": {
                "defaults": {
                  "unit": "celsius",
                  "thresholds": {
                    "mode": "absolute",
                    "steps": [
                      {
                        "value": 0,
                        "color": "green"
                      },
                      {
                        "value": 80,
                        "color": "red"
                      }
                    ]
                  },
                  "color": {
                    "mode": "palette-classic"
                  },
                  "custom": {
                    "axisBorderShow": false,
                    "axisCenteredZero": false,
                    "axisColorMode": "text",
                    "axisLabel": "",
                    "axisPlacement": "auto",
                    "barAlignment": 0,
                    "barWidthFactor": 0.6,
                    "drawStyle": "line",
                    "fillOpacity": 0,
                    "gradientMode": "none",
                    "hideFrom": {
                      "legend": false,
                      "tooltip": false,
                      "viz": false
                    },
                    "insertNulls": false,
                    "lineInterpolation": "linear",
                    "lineWidth": 1,
                    "pointSize": 5,
                    "scaleDistribution": {
                      "type": "linear"
                    },
                    "showPoints": "auto",
                    "showValues": false,
                    "spanNulls": false,
                    "stacking": {
                      "group": "A",
                      "mode": "none"
                    },
                    "thresholdsStyle": {
                      "mode": "off"
                    }
                  }
                },
                "overrides": []
              }
            }
          }
        }
      },
      "panel-4": {
        "kind": "Panel",
        "spec": {
          "id": 4,
          "title": "Raspberry Pi – Node Status (Online/Offline)",
          "description": "",
          "links": [],
          "data": {
            "kind": "QueryGroup",
            "spec": {
              "queries": [
                {
                  "kind": "PanelQuery",
                  "spec": {
                    "query": {
                      "kind": "DataQuery",
                      "group": "prometheus",
                      "version": "v0",
                      "datasource": {
                        "name": "grafanacloud-prom"
                      },
                      "spec": {
                        "editorMode": "code",
                        "exemplar": false,
                        "expr": "up{job=\"node\"}",
                        "instant": true,
                        "legendFormat": "{{instance}}",
                        "range": false
                      }
                    },
                    "refId": "A",
                    "hidden": false
                  }
                }
              ],
              "transformations": [],
              "queryOptions": {}
            }
          },
          "vizConfig": {
            "kind": "VizConfig",
            "group": "stat",
            "version": "13.4.0-44730370174",
            "spec": {
              "options": {
                "colorMode": "value",
                "graphMode": "none",
                "justifyMode": "auto",
                "orientation": "auto",
                "percentChangeColorMode": "standard",
                "reduceOptions": {
                  "calcs": [
                    "lastNotNull"
                  ],
                  "fields": "",
                  "values": true
                },
                "showPercentChange": false,
                "textMode": "value_and_name",
                "wideLayout": true
              },
              "fieldConfig": {
                "defaults": {
                  "mappings": [
                    {
                      "type": "value",
                      "options": {
                        "0": {
                          "text": "Offline",
                          "color": "dark-red",
                          "index": 1
                        },
                        "1": {
                          "text": "Online",
                          "color": "semi-dark-green",
                          "index": 0
                        }
                      }
                    }
                  ],
                  "thresholds": {
                    "mode": "absolute",
                    "steps": [
                      {
                        "value": 0,
                        "color": "green"
                      }
                    ]
                  },
                  "color": {
                    "mode": "thresholds"
                  }
                },
                "overrides": []
              }
            }
          }
        }
      },
      "panel-8": {
        "kind": "Panel",
        "spec": {
          "id": 8,
          "title": "Raspberry Pi – Network Traffic (Bytes/s)",
          "description": "",
          "links": [],
          "data": {
            "kind": "QueryGroup",
            "spec": {
              "queries": [
                {
                  "kind": "PanelQuery",
                  "spec": {
                    "query": {
                      "kind": "DataQuery",
                      "group": "prometheus",
                      "version": "v0",
                      "datasource": {
                        "name": "grafanacloud-prom"
                      },
                      "spec": {
                        "editorMode": "code",
                        "expr": "sum by (instance) (\n  rate(node_network_receive_bytes_total{job=\"node\",device!=\"lo\"}[5m])\n)",
                        "legendFormat": "RX {{instance}}",
                        "range": true
                      }
                    },
                    "refId": "A",
                    "hidden": false
                  }
                },
                {
                  "kind": "PanelQuery",
                  "spec": {
                    "query": {
                      "kind": "DataQuery",
                      "group": "prometheus",
                      "version": "v0",
                      "datasource": {
                        "name": "grafanacloud-prom"
                      },
                      "spec": {
                        "editorMode": "code",
                        "expr": "sum by (instance) (\n  rate(node_network_transmit_bytes_total{job=\"node\",device!=\"lo\"}[5m])\n)",
                        "instant": false,
                        "legendFormat": "TX {{instance}}",
                        "range": true
                      }
                    },
                    "refId": "B",
                    "hidden": false
                  }
                }
              ],
              "transformations": [],
              "queryOptions": {}
            }
          },
          "vizConfig": {
            "kind": "VizConfig",
            "group": "timeseries",
            "version": "13.4.0-44730370174",
            "spec": {
              "options": {
                "legend": {
                  "calcs": [],
                  "displayMode": "list",
                  "placement": "bottom",
                  "showLegend": true
                },
                "tooltip": {
                  "hideZeros": false,
                  "mode": "single",
                  "sort": "none"
                }
              },
              "fieldConfig": {
                "defaults": {
                  "unit": "Bps",
                  "min": 0,
                  "thresholds": {
                    "mode": "absolute",
                    "steps": [
                      {
                        "value": 0,
                        "color": "green"
                      },
                      {
                        "value": 80,
                        "color": "red"
                      }
                    ]
                  },
                  "color": {
                    "mode": "palette-classic"
                  },
                  "custom": {
                    "axisBorderShow": false,
                    "axisCenteredZero": false,
                    "axisColorMode": "text",
                    "axisLabel": "",
                    "axisPlacement": "auto",
                    "barAlignment": 0,
                    "barWidthFactor": 0.6,
                    "drawStyle": "line",
                    "fillOpacity": 0,
                    "gradientMode": "none",
                    "hideFrom": {
                      "legend": false,
                      "tooltip": false,
                      "viz": false
                    },
                    "insertNulls": false,
                    "lineInterpolation": "linear",
                    "lineWidth": 1,
                    "pointSize": 5,
                    "scaleDistribution": {
                      "type": "linear"
                    },
                    "showPoints": "auto",
                    "showValues": false,
                    "spanNulls": false,
                    "stacking": {
                      "group": "A",
                      "mode": "none"
                    },
                    "thresholdsStyle": {
                      "mode": "off"
                    }
                  }
                },
                "overrides": []
              }
            }
          }
        }
      },
      "panel-9": {
        "kind": "Panel",
        "spec": {
          "id": 9,
          "title": "Raspberry Pi – Storage Usage (%)",
          "description": "",
          "links": [],
          "data": {
            "kind": "QueryGroup",
            "spec": {
              "queries": [
                {
                  "kind": "PanelQuery",
                  "spec": {
                    "query": {
                      "kind": "DataQuery",
                      "group": "prometheus",
                      "version": "v0",
                      "datasource": {
                        "name": "grafanacloud-prom"
                      },
                      "spec": {
                        "editorMode": "code",
                        "exemplar": false,
                        "expr": "100 * (\n  1 - (\n    node_filesystem_avail_bytes{job=\"node\",mountpoint=\"/\"}\n    /\n    node_filesystem_size_bytes{job=\"node\",mountpoint=\"/\"}\n  )\n)",
                        "instant": true,
                        "legendFormat": "{{instance}}",
                        "range": false
                      }
                    },
                    "refId": "A",
                    "hidden": false
                  }
                }
              ],
              "transformations": [],
              "queryOptions": {}
            }
          },
          "vizConfig": {
            "kind": "VizConfig",
            "group": "bargauge",
            "version": "13.4.0-44730370174",
            "spec": {
              "options": {
                "displayMode": "gradient",
                "legend": {
                  "calcs": [],
                  "displayMode": "list",
                  "placement": "bottom",
                  "showLegend": false
                },
                "maxVizHeight": 300,
                "minVizHeight": 16,
                "minVizWidth": 8,
                "namePlacement": "auto",
                "orientation": "auto",
                "reduceOptions": {
                  "calcs": [
                    "lastNotNull"
                  ],
                  "fields": "",
                  "values": true
                },
                "showUnfilled": true,
                "sizing": "auto",
                "textMode": "auto",
                "valueMode": "color"
              },
              "fieldConfig": {
                "defaults": {
                  "unit": "percent",
                  "decimals": 0,
                  "min": 0,
                  "max": 100,
                  "thresholds": {
                    "mode": "absolute",
                    "steps": [
                      {
                        "value": 0,
                        "color": "green"
                      },
                      {
                        "value": 70,
                        "color": "#EAB839"
                      },
                      {
                        "value": 85,
                        "color": "dark-red"
                      }
                    ]
                  },
                  "color": {
                    "mode": "thresholds"
                  }
                },
                "overrides": []
              }
            }
          }
        }
      }
    },
    "layout": {
      "kind": "AutoGridLayout",
      "spec": {
        "maxColumnCount": 3,
        "columnWidthMode": "standard",
        "rowHeightMode": "standard",
        "items": [
          {
            "kind": "AutoGridLayoutItem",
            "spec": {
              "element": {
                "kind": "ElementReference",
                "name": "panel-1"
              }
            }
          },
          {
            "kind": "AutoGridLayoutItem",
            "spec": {
              "element": {
                "kind": "ElementReference",
                "name": "panel-2"
              }
            }
          },
          {
            "kind": "AutoGridLayoutItem",
            "spec": {
              "element": {
                "kind": "ElementReference",
                "name": "panel-3"
              }
            }
          },
          {
            "kind": "AutoGridLayoutItem",
            "spec": {
              "element": {
                "kind": "ElementReference",
                "name": "panel-4"
              }
            }
          },
          {
            "kind": "AutoGridLayoutItem",
            "spec": {
              "element": {
                "kind": "ElementReference",
                "name": "panel-8"
              }
            }
          },
          {
            "kind": "AutoGridLayoutItem",
            "spec": {
              "element": {
                "kind": "ElementReference",
                "name": "panel-9"
              }
            }
          }
        ]
      }
    },
    "links": [],
    "liveNow": false,
    "preload": false,
    "tags": [],
    "timeSettings": {
      "timezone": "browser",
      "from": "now-6h",
      "to": "now",
      "autoRefresh": "",
      "autoRefreshIntervals": [
        "5s",
        "10s",
        "30s",
        "1m",
        "5m",
        "15m",
        "30m",
        "1h",
        "2h",
        "1d"
      ],
      "hideTimepicker": false,
      "fiscalYearStartMonth": 0
    },
    "title": "Drone Detection – System Monitoring",
    "variables": [],
    "preferences": {
      "layout": {
        "kind": "AutoGridLayout",
        "spec": {
          "maxColumnCount": 3,
          "columnWidthMode": "standard",
          "rowHeightMode": "standard",
          "items": []
        }
      }
    }
  }
}
