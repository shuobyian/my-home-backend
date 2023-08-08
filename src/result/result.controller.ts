import { Controller, Get, Post, Query } from '@nestjs/common';
import { ResultService } from 'src/result/result.service';

@Controller('result')
export class ResultController {
  constructor(private readonly resultService: ResultService) {}

  @Post()
  createAll() {
    return this.resultService.createAll();
  }

  @Get()
  findAll(@Query('name') name?: string) {
    return this.resultService.findOneByName(name);
  }
}
