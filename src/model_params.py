import argparse
import torch
import parse_nk
def torch_load(load_path):
    if parse_nk.use_cuda:
        return torch.load(load_path)
    else:
        return torch.load(load_path, map_location=lambda storage, location: storage)
def print_model_parameters(model_path):
    print("Loading model from {}...".format(model_path))
    assert model_path.endswith(".pt"), "Only pytorch savefiles supported"

    info = torch_load(args.model_path_base)
    assert 'hparams' in info['spec'], "Older savefiles not supported"
    parser = parse_nk.NKChartParser.from_spec(info['spec'], info['state_dict'])
    trainable_parameters = [param for param in parser.parameters() if param.requires_grad]
    total = sum([param.nelement() for param in trainable_parameters])
    print("Number of parameter: %.3fM" % (total / 1e6))
    param_list = list(parser.named_parameters())
    for i in param_list:
        print(i[0], i[1].data.shape)
if __name__=='__main__':
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--model_path_base', default='../../models_dev=3.51.pt')
    args = argparser.parse_args()
    print_model_parameters(args.model_path_base)