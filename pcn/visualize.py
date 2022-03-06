
from mesa.visualization.ModularVisualization import VisualizationElement


class NetworkModule(VisualizationElement):
    # package_includes = ["sigma.min.js"]
    # local_includes = [
    #     "js/settings.js",
    #     "js/sigma.canvas.edges.labels.def.js",
    #     "js/sigma.canvas.edges.labels.curve.js",
    #     "js/sigma.canvas.edges.labels.curvedArrow.js",
    #     "js/NetworkModule_sigma.js"
    # ]
    package_includes = ["d3.min.js"]
    local_includes = [
        "js/NetworkModule_d3.js",
        "js/hide.js"
    ]
        
    def __init__(
        self, portrayal_method, canvas_height=500, canvas_width=500
    ):
        self.portrayal_method = portrayal_method
        self.canvas_height = canvas_height
        self.canvas_width = canvas_width
        new_element = "new NetworkModule({}, {})".format(
            self.canvas_width, self.canvas_height
        )
        self.js_code = "elements.push(" + new_element + ");"

    def render(self, model):
        return self.portrayal_method(model.network.G)
