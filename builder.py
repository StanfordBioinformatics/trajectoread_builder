#!/usr/bin/env python

import os
import re
import ast
import sys
import pdb
import dxpy
import json
import stat
import shutil
import fnmatch
import logging
import argparse
import datetime
import subprocess

from dxpy import app_builder

class WorkflowBuild:
    '''Build workflow on DNAnexus.

    Build a workflow using local DNAnexus applet source files and a
    JSON configuration file.

    Args:
        workflow_config_path (str): Path of workflow configuration JSON file.
        region (str): DNAnexus region.
        project_dxid (str): DNAnexus project ID.
        dx_folder (str): DNAnexus project folder name.
        dry_run (bool): Dry-run does not build any DNAnexus objects.
    
    Attributes:
        region (str): DNAnexus region.
        project_dxid (str): DNAnexus project ID.
        dx_folder (str): DNAnexus project folder name.
        applet_dxids (dict): IDs of DNAnexus applets.
        self.name (str): Workflow name.
        self.object (DXWorkflow): DNAnexus workflow object.
        self.object_dxid (str): DNAnexus workflow ID.
        self.edit_version (int): Workflow edit version; for updating stages.
        logger (Logger)



    '''

    def __init__(
                 self, 
                 workflow_config_path, 
                 region, 
                 project_dxid, 
                 dx_folder, 
                 dry_run):

        self.region = region
        self.project_dxid = project_dxid
        self.dx_folder = dx_folder

        # Get from workflow JSON
        self.name = None
        self.details = None
        self.properties = None
        self.tags = None

        # Generate at runtime
        self.workflow = None
        self.workflow_dxid = None
        self.stages = {}
        self.applet_dxids = {}

        # Configure loggers for BuildWorkflow and Applet classes
        self.logger = config_logger('Build Workflow')

        # Logic for choosing applet path in DXProject; used by Applet:write_config_file()
        self.logger.info('Designated workflow path: {}:{}'.format(
                                                                  project_dxid, 
                                                                  dx_folder))

        # Parse workflow information from configuration file
        with open(workflow_config_path, 'r') as CONFIG:
            workflow_config = json.load(CONFIG)
        self.details = workflow_config['details']
        self.properties = workflow_config['properties']
        self.tags = workflow_config['tags']
        self.stages_config = workflow_config['stages']
        self.name = self.details['name']

        # Create DXWorkflow object on DNAnexus
        self.workflow = dxpy.new_dxworkflow(
                                            title = self.name,
                                            name = self.name,
                                            project = self.project_dxid,
                                            folder = self.dx_folder,
                                            properties = self.properties,
                                            details = self.details,
                                            tags = self.tags)
        self.workflow_dxid = self.workflow.describe()['id']

        # Build applets and create workflow stages
        for stage_index in range(0, len(self.stages_config)):
            stage_index = str(stage_index)
            stage = WorkflowStage(self.workflow, stage_index)

            applet_name = self.stages_config[stage_index]['executable']
            applet = AppletBuild(
                                 applet_path = applet_name,
                                 region = region,
                                 project_dxid = project_dxid,
                                 dx_folder = dx_folder,
                                 dry_run = dry_run)
            self.applet_dxids[applet_name] = applet.dxid
            
            # Add stage to DNAnexus workflow object
            self.logger.info('Creating workflow stage for {}'.format(applet_name))
            output_folder = self.stages_config[stage_index]['folder']
            stage.create(applet.dxid, output_folder)
            self.stages[stage_index] = stage

        # Add inputs to each workflow stage
        for stage_index in range(0, len(self.stages)):
            self.logger.info('Setting inputs for stage {}'.format(stage_index))
            stage_index = str(stage_index)
            stage = self.stages[stage_index]

            standard_inputs = self.stages_config[stage_index]['input']
            linked_inputs = self.stages_config[stage_index]['linked_input']
            stage.set_inputs(self.stages, standard_inputs, linked_inputs)
        
        dxpy.api.workflow_close(self.workflow_dxid)
        self.logger.info('Build complete: {} ,'.format(self.name) +
                         'workflow id: {}:{}'.format(
                                                     self.project_dxid,
                                                     self.workflow_dxid))

class WorkflowStage:

    def __init__(self, workflow, stage_index):

        self.workflow = workflow
        self.index = stage_index
        self.dxid = None 

    def create(self, applet_dxid, output_folder):
        '''Add new stage to DNAnexus workflow.

        Args:
            applet_dxid (str): Stage applet dxid.
            output_folder (str): Applet output folder.

        Returns:
            self.dxid (str): Stage dxid.
        '''

        edit_version = self.workflow.describe()['editVersion']
        self.dxid = self.workflow.add_stage(
                                            edit_version = edit_version,
                                            executable = applet_dxid,
                                            folder = output_folder)
        return self.dxid

    def set_inputs(self, stages, standard_inputs, linked_inputs):
        '''Set inputs to workflow stage.

        Args:
            stages (dict?): Dictionary of WorkflowStage objects.
            std_inputs (dict): Static input values or links to 
                              objects in DX Object Store.
            linked_inputs (dict): Input objects that are generated as 
                                 output of previous workflow stages.
        '''
        
        stage_input = {}
        if not self.dxid:
            logger.error('Stage %s has not yet been created' % stage_index)

        for key, value in standard_inputs.iteritems():
            stage_input[key] = value

        for field_name in linked_inputs:
            linked_input = linked_inputs[field_name]
            if type(linked_input) is dict:
                field_type = linked_input['field']
                input_stage_index = linked_input['stage']
                input_stage_dxid = stages[input_stage_index].dxid
                stage_input[field_name] = {'$dnanexus_link': {
                                                              'stage': input_stage_dxid,
                                                              field_type: field_name
                                                             }
                                          }
            elif type(linked_input) is list:
                stage_input[field_name] = []
                for list_input in linked_input:
                    field_type = list_input['field']
                    input_stage_index = list_input['stage']
                    input_stage_dxid = stages[input_stage_index].dxid
                    stage_input[field_name].append({
                                                    '$dnanexus_link': {
                                                                       'stage': input_stage_dxid,
                                                                       field_type: field_name
                                                                      }
                                                   })

        edit_version = self.workflow.describe()['editVersion']
        self.workflow.update_stage(
                                   stage = self.index,
                                   edit_version = edit_version,
                                   stage_input = stage_input)
        return stage_input

class AppletBuild:

    def __init__(self, applet_path, region, project_dxid, dx_folder, dry_run):

        self.logger = config_logger('Build {}'.format(applet_path))
        self.dxid = None
        
        dxapp_path = os.path.join(applet_path, 'dxapp.json')
        with open(dxapp_path, 'r') as DXAPP:
            dxapp_json = json.load(DXAPP)  
            
        #version = dxapp_json['details']['upstreamVersion']
        name = dxapp_json['name'] 
        dx_folder = os.path.join(dx_folder) 
        dx_applet_path = os.path.join(dx_folder, name)  

        # Ensure folder exists on DNAnexus
        dx_project = dxpy.DXProject(project_dxid)
        try:
            dx_project.new_folder(dx_folder)
        except:
            self.logger.info(
                             "Folder '%s'" % dx_folder +
                             " in project: '%s'" % project_dxid +
                             ' already exists.')

        build_args = [
                      'dx',
                      'build',
                      '%s' % applet_path, 
                      '-d=%s:%s' % (project_dxid, dx_applet_path),
                      '-f']

        if dry_run:
            build_args.append('-n')
        self.logger.info(build_args)

        result = subprocess.check_output(build_args)
        if dry_run:
            print result
            return
        result = ast.literal_eval(result)
        self.dxid = result['id']

        applet_name = os.path.basename(applet_path)
        if dry_run:
            self.logger.info(result)
        else:
            self.logger.info('Build complete. {} applet id: {}.'.format(
                                                                       name, 
                                                                       result['id']))

def config_logger(name):
    '''Create simple logger.

    https://docs.python.org/2/howto/logging.html
    '''

    # create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)

    return logger

def _make_new_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def parse_args(args):

    parser = argparse.ArgumentParser()
    parser.add_argument(
                        '-a', 
                        '--applet', 
                        dest='applet_path', 
                        type=str,
                        help='Name of applet folder.')
    parser.add_argument(
                        '-w', 
                        '--workflow', 
                        dest='workflow_path', 
                        type=str,
                        help='Path of workflow JSON file.')
    parser.add_argument(
                        '-e',
                        '--environment',
                        dest = 'env',
                        type = str,
                        choices = ['develop', 'production'],
                        default = 'develop',
                        help = 'Select DNAnexus environment.')
    parser.add_argument(
                        '-d',
                        '--dry-run',
                        dest = 'dry_run',
                        action = 'store_true',
                        default = False,
                        help = 'Does not actually create applet or workflow')
    parser.add_argument(
                        '-r',
                        '--region',
                        dest = 'region',
                        type = str,
                        choices = ['azure:westus','aws:us-east-1'],
                        default = 'azure:westus',
                        help = 'Choose DNAnexus region')
    if len(sys.argv[1:]) < 1:
        #logger.warning('No arguments specified')
        parser.print_help()
        #sys.exit()
        return None
    args = parser.parse_args(args)
    return(args)

def main():

    logger = config_logger('Main')

    home = os.path.dirname(os.path.abspath(__file__))
    build_json = os.path.join(home, 'builder.json')

    # Parse arguments
    args = parse_args(sys.argv[1:])
    if not args:
        logger.error('No arguments provided')
        sys.exit()
    else:
        logger.info('Args: %s' % args)
    
    if args.applet_path and args.workflow_path:
        main_logger.error(
                     'Applet and workflow arguments passed to builder. ' +
                     'Can only build one object at once')
        sys.exit()    
    elif not args.applet_path and not args.workflow_path:
        main_logger.error('No valid DNAnexus objects specified for building')
        sys.exit()

    if args.applet_path:
        type = 'applet'
    elif args.workflow_path:
        type = 'workflow'
    else:
        print 'No object type found to build'

    # Initiate path list and global resource manager objects
    #path_list = PathList()

    # Read 'builder.json' configuration file for building workflows/applets
    with open(build_json, 'r') as json_fh:
        build_config = json.load(json_fh)
        project_dxid = build_config['region'][args.region][type][args.env]['dxid']
        dx_folder = build_config['region'][args.region][type][args.env]['folder']

    # Create build object
    if args.applet_path:
        logger.info('Building applet: %s' % args.applet_path)
        builder = AppletBuild(
                              applet_path = args.applet_path,
                              region = args.region,
                              project_dxid = project_dxid,
                              dx_folder = dx_folder,
                              dry_run = args.dry_run)
    elif args.workflow_path:
        logger.info('Building workflow: %s' % args.workflow_path)
        builder = WorkflowBuild(
                                workflow_config_path = args.workflow_path,
                                region = args.region,
                                project_dxid = project_dxid,
                                dx_folder = dx_folder,
                                dry_run = args.dry_run)
        
if __name__ == "__main__":
    main() 
