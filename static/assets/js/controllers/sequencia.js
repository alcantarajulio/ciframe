angular.module('deciframeApp').controller('SequenciaController', function($http, $window, ngProgressFactory, $anchorScroll, $location, GENEROS) {
  var COR_SEQUENCIA = '#2E1C74';

  var montarSequencia = function(linha) {
    var acordes = [];
    for (var i = 0; i < linha.acordes.length; i++) {
      acordes.push({ 'acorde': linha.acordes[i], 'cor': COR_SEQUENCIA });
    }
    return {
      'id': linha.id,
      'acordes': acordes,
      'total_musicas': linha.total_musicas
    };
  };

  var vm = this;
  vm.sequenciasFamosas = [];
  vm.acordesDisponiveis = [];
  vm.novaSequencia = "";
  vm.erroCadastro = null;
  vm.minhaSequencia = {};
  vm.isSearching = false;
  vm.showSearchResultsCount = false;
  vm.esfigeSpeech =  "";
  vm.musics = [];
  vm.totalMusicas = 0;
  vm.temMaisPaginas = false;
  vm.generos = GENEROS;
  vm.meuGenero = "";
  vm.progressbar = ngProgressFactory.createInstance();

  vm.carregarSequencias = function(idSelecionado) {
    $http.get('/sequencias')
      .success(function(data) {
        vm.sequenciasFamosas = [];
        for (var i = 0; i < data.length; i++) {
          vm.sequenciasFamosas.push(montarSequencia(data[i]));
        }
        if (idSelecionado) {
          for (var j = 0; j < vm.sequenciasFamosas.length; j++) {
            if (vm.sequenciasFamosas[j].id === idSelecionado) {
              vm.pesquisarPorSequencia(vm.sequenciasFamosas[j]);
              break;
            }
          }
        }
      });
  };

  vm.carregarAcordes = function() {
    $http.get('/acordes')
      .success(function(data) {
        vm.acordesDisponiveis = data;
      });
  };

  vm.temAcorde = function(acorde) {
    if (vm.minhaSequencia.acordes) {
      return (vm.minhaSequencia.acordes.indexOf(acorde) > -1);
    } else {
      return false;
    }
  }

  var createChordsString = function(chords) {
    var str = "";
    for (var i = 0; i < chords.length; i++) {
      // o dataset tem acordes com '#', '+' e '%': sem codificar, o '#' corta a
      // URL, o '+' chega como espaço e o '%' gera query malformada
      str = str.concat(encodeURIComponent(chords[i].acorde), ',');
    }
    return str.substring(0, str.length-1);
  }

  vm.pesquisarPorSequencia = function(sequencia) {
    if (sequencia) {
      vm.minhaSequencia = sequencia;
    }
    vm.progressbar.start();
    vm.esfigeSpeech = "Procurando músicas com base na sequencia...";
    vm.isSearching = true;
    vm.musics = [];
    vm.totalMusicas = 0;
    vm.temMaisPaginas = false;

    var apiUrl = "";
    var searchString = "similares?sequencia=".concat(createChordsString(vm.minhaSequencia.acordes));
    if (vm.meuGenero !== "" && vm.meuGenero !== null) {
      // gêneros como "R&B;" também precisam de codificação
      searchString += "&generos="+encodeURIComponent(vm.meuGenero);
    }
    $http.get(apiUrl.concat(searchString))
      .success(function(data) {
        vm.progressbar.complete();
        vm.isSearching = false;
        vm.musics = data;
        if (!data.length) {
          // com filtro de gênero a sequência pode ter resultados fora dele;
          // a mensagem não pode dizer que não existe nenhuma música
          vm.esfigeSpeech = (vm.meuGenero === "" || vm.meuGenero === null)
            ? "Nenhuma música tem essa sequência"
            : "Nenhuma música desse gênero tem essa sequência";
          vm.showSearchResultsCount = false;
          return;
        }
        vm.esfigeSpeech = "Encontrei essas músicas";
        vm.showSearchResultsCount = true;
        // total_musicas do catálogo não considera o filtro de gênero; sem
        // filtro, é o total real e a API devolve no máximo 100 por página
        if (vm.meuGenero === "" || vm.meuGenero === null) {
          vm.totalMusicas = vm.minhaSequencia.total_musicas || data.length;
          vm.temMaisPaginas = vm.totalMusicas > data.length;
        }
      })
      .error(function(data) {
        vm.progressbar.complete();
        vm.esfigeSpeech = "Ops! Algo errado.";
        vm.isSearching = false;
        vm.showSearchResultsCount = false;
      });
  }

  vm.cadastrarSequencia = function() {
    vm.erroCadastro = null;
    var tokens = (vm.novaSequencia || "").split(/[\s,;]+/);
    var acordes = [];
    for (var i = 0; i < tokens.length; i++) {
      if (tokens[i]) {
        acordes.push(tokens[i]);
      }
    }
    if (!acordes.length) {
      vm.erroCadastro = { 'erro': 'sequencia_vazia' };
      return;
    }
    $http.post('/sequencias', { 'acordes': acordes })
      .success(function(data) {
        vm.novaSequencia = "";
        vm.carregarSequencias(data.id);
      })
      .error(function(data) {
        if (data && data.erro) {
          vm.erroCadastro = data;
        } else {
          vm.erroCadastro = { 'erro': 'falha' };
        }
      });
  };

  vm.limparErro = function() {
    vm.erroCadastro = null;
  };

  vm.aplicarSugestao = function(item, sugestao) {
    // troca no texto do formulário só o token recusado, preservando o resto
    var partes = (vm.novaSequencia || "").split(/([\s,;]+)/);
    for (var i = 0; i < partes.length; i++) {
      if (partes[i] === item.acorde) {
        partes[i] = sugestao;
      }
    }
    vm.novaSequencia = partes.join("");
    vm.erroCadastro = null;
  };

  vm.limparPesquisa = function() {
    vm.minhaSequencia = {};
    vm.musics = [];
  }

  vm.goToLirics = function(music) {
    $window.open(music.url);
  };

  vm.goToResults = function() {
    vm.showSearchResultsCount = false;
    $("body").animate({scrollTop: $("#results").offset().top}, "slow");
  };

  vm.carregarSequencias();
  vm.carregarAcordes();
});
